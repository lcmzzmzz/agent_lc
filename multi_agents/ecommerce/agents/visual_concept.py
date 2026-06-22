from __future__ import annotations

from pathlib import Path
from typing import Any

from collections.abc import Awaitable, Callable

from multi_agents.ecommerce.runtime.policy_guard import redact_secrets
from multi_agents.ecommerce.runtime.trace_recorder import (
    emit_trace,
    finish_trace_node,
    start_trace_node,
)
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationProvider,
    ImageGenerationRequest,
)
from multi_agents.ecommerce.tools.image_generation.volc_ark_jimeng import (
    VolcArkJimengProvider,
)

DEFAULT_VISUAL_MODEL = "doubao-seedream-4-5-251128"
ProgressFn = Callable[[str, dict], Awaitable[None]]

SLOTS = [
    ("product_concept", "appearance", "visual_product_01"),
    ("product_concept", "use_case", "visual_product_02"),
    ("product_concept", "detail", "visual_product_03"),
    ("listing", "main_image", "visual_listing_01"),
    ("listing", "infographic", "visual_listing_02"),
    ("listing", "lifestyle", "visual_listing_03"),
]


def _selected_slots(image_count: int) -> list[tuple[str, str, str]]:
    if image_count <= 1:
        return [("listing", "main_image", "visual_listing_01")]
    if image_count <= 3:
        return [
            ("product_concept", "appearance", "visual_product_01"),
            ("listing", "main_image", "visual_listing_01"),
            ("listing", "lifestyle", "visual_listing_03"),
        ]
    return SLOTS[:6]


def build_visual_brief(state: EcommerceResearchState) -> dict[str, Any]:
    query = state.get("query", "")
    review = state.get("review_result", {})
    competitor = state.get("competitor_result", {})
    score = state.get("opportunity_score", {})
    pain_points = review.get("pain_points", [])[:3]
    gaps = competitor.get("gaps", [])[:3]
    return {
        "product_positioning": f"{query} product concept for {state.get('target_market', 'US')} ecommerce buyers",
        "target_customer": "buyers matching the observed trend and review pain points",
        "design_direction": ", ".join([*gaps, *pain_points]) or score.get("recommendation", ""),
        "differentiation": gaps,
        "risk_notes": score.get("risks", []) or ["avoid brand logos", "avoid medical claims", "avoid exaggerated promises"],
    }


def _prompt_for_slot(
    *,
    state: EcommerceResearchState,
    kind: str,
    slot: str,
    brief: dict[str, Any],
) -> tuple[str, str, str, list[str]]:
    query = state.get("query", "")
    pain_points = state.get("review_result", {}).get("pain_points", [])[:3]
    gaps = state.get("competitor_result", {}).get("gaps", [])[:3]
    reason_parts = [*gaps, *pain_points]
    reason = " / ".join(str(item) for item in reason_parts if item) or "derived from ecommerce research evidence"
    source_refs = ["review_result.pain_points", "competitor_result.gaps"]
    negative = "brand logo, medical claims, exaggerated promises, watermark, distorted product, unreadable text"
    if kind == "listing" and slot == "main_image":
        prompt = (
            f"Amazon main image draft for {query}. Pure white background, single product centered, "
            f"premium clean ecommerce product photography, clear shape and material, no text, no logo. "
            f"Design direction: {brief.get('design_direction', '')}. Avoid medical claims."
        )
    elif kind == "listing" and slot == "infographic":
        prompt = (
            f"Amazon listing infographic concept for {query}. Show simple visual callouts for key benefits: "
            f"{brief.get('design_direction', '')}. Use clean layout, minimal readable text, realistic product render, "
            f"no brand logo, no exaggerated claims."
        )
    elif kind == "listing" and slot == "lifestyle":
        prompt = (
            f"Lifestyle ecommerce scene for {query}. Show the product used by the target customer in a realistic daily scenario, "
            f"natural light, premium but believable, emphasize convenience and differentiation: {brief.get('design_direction', '')}."
        )
    elif slot == "detail":
        prompt = (
            f"Detailed product concept render for {query}. Focus on differentiated functional details: "
            f"{brief.get('design_direction', '')}. Macro product photography, clean background, realistic materials."
        )
    elif slot == "use_case":
        prompt = (
            f"Product use case concept image for {query}. Show the product in context with a realistic customer scenario, "
            f"clean modern ecommerce style, emphasize pain point solutions: {brief.get('design_direction', '')}."
        )
    else:
        prompt = (
            f"High quality ecommerce product concept render for {query}. "
            f"Design direction: {brief.get('design_direction', '')}. "
            f"Premium realistic product photography, clean background, no logo, no watermark."
        )
    return prompt, negative, reason, source_refs


def build_visual_prompts(
    state: EcommerceResearchState,
    *,
    image_count: int,
) -> list[dict[str, Any]]:
    brief = build_visual_brief(state)
    prompts: list[dict[str, Any]] = []
    for kind, slot, asset_id in _selected_slots(max(1, min(6, int(image_count)))):
        prompt, negative, reason, source_refs = _prompt_for_slot(
            state=state,
            kind=kind,
            slot=slot,
            brief=brief,
        )
        prompts.append(
            {
                "asset_id": asset_id,
                "kind": kind,
                "slot": slot,
                "prompt": prompt,
                "negative_prompt": negative,
                "reason": reason,
                "source_refs": source_refs,
            }
        )
    return prompts


def _asset_from_result(prompt_row: dict[str, Any], result: Any) -> dict[str, Any]:
    return {
        **prompt_row,
        "status": result.status,
        "remote_url": result.remote_url,
        "local_path": result.local_path,
        "mime_type": result.mime_type,
        "width": result.width,
        "height": result.height,
        "model": result.model,
        "duration_ms": result.duration_ms,
        "usage": result.usage,
        "warning": result.warning,
    }


def _failed_asset_from_exception(
    prompt_row: dict[str, Any],
    exc: Exception,
    *,
    model: str,
) -> dict[str, Any]:
    redacted = redact_secrets({"error": str(exc)})
    return {
        **prompt_row,
        "status": "failed",
        "remote_url": "",
        "local_path": "",
        "mime_type": "",
        "width": 0,
        "height": 0,
        "model": model,
        "duration_ms": 0,
        "usage": {},
        "warning": str(redacted.get("error", "")),
    }


async def run_visual_concept_agent(
    state: EcommerceResearchState,
    *,
    image_provider: ImageGenerationProvider | None = None,
    visual_enabled: bool = False,
    visual_model: str = DEFAULT_VISUAL_MODEL,
    visual_size: str = "2K",
    visual_watermark: bool = False,
    image_count: int = 6,
    output_dir: str | Path | None = None,
    progress_callback: ProgressFn | None = None,
) -> EcommerceResearchState:
    trace_idx = start_trace_node(
        state,
        node="visual",
        agent="VisualConceptAgent",
        input_summary={
            "query": state.get("query", ""),
            "model": visual_model,
            "requested_image_count": image_count,
            "trend_score": state.get("trend_result", {}).get("trend_score"),
            "overall_score": state.get("opportunity_score", {}).get("overall_score"),
        },
    )
    if not visual_enabled:
        state["visual_result"] = {
            "enabled": False,
            "status": "skipped",
            "visual_brief": {},
            "prompts": [],
            "assets": [],
            "warnings": [],
            "usage": {},
        }
        record = finish_trace_node(state, trace_idx, status="skipped", output_summary={"prompt_count": 0})
        await emit_trace(progress_callback, record)
        return state

    brief = build_visual_brief(state)
    prompts = build_visual_prompts(state, image_count=image_count)
    visual_dir = Path(output_dir or ".")
    provider = image_provider or VolcArkJimengProvider(output_dir=visual_dir)
    assets: list[dict[str, Any]] = []
    warnings: list[str] = []
    usage = {"generated_images": 0, "total_tokens": 0, "failed_images": 0}
    for prompt_row in prompts:
        try:
            result = await provider.generate(
                ImageGenerationRequest(
                    asset_id=prompt_row["asset_id"],
                    prompt=prompt_row["prompt"],
                    model=visual_model,
                    size=visual_size,
                    watermark=visual_watermark,
                )
            )
            asset = _asset_from_result(prompt_row, result)
        except Exception as exc:
            asset = _failed_asset_from_exception(prompt_row, exc, model=visual_model)
        assets.append(asset)
        if asset["status"] == "success":
            asset_usage = asset.get("usage", {})
            usage["generated_images"] += int(asset_usage.get("generated_images", 0) or 0)
            usage["total_tokens"] += int(asset_usage.get("total_tokens", 0) or 0)
        else:
            usage["failed_images"] += 1
            if asset.get("warning"):
                warnings.append(str(asset["warning"]))

    success_count = sum(1 for row in assets if row.get("status") == "success")
    status = "success" if success_count == len(assets) else ("partial" if success_count else "failed")
    state["visual_result"] = {
        "enabled": True,
        "status": status,
        "model": visual_model,
        "provider": "volcengine_ark_jimeng",
        "visual_brief": brief,
        "prompts": prompts,
        "assets": assets,
        "warnings": warnings,
        "usage": usage,
    }
    record = finish_trace_node(
        state,
        trace_idx,
        status=status,
        output_summary={
            "prompt_count": len(prompts),
            "generated_image_count": success_count,
            "failed_image_count": usage["failed_images"],
            "total_tokens": usage["total_tokens"],
        },
        warnings=warnings,
    )
    await emit_trace(progress_callback, record)
    return state
