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


def _competitor_differentiation(competitor: dict[str, Any], *, limit: int = 3) -> list[str]:
    values = competitor.get("differentiation_opportunities") or competitor.get("gaps") or []
    if isinstance(values, str):
        candidates = [values]
    elif isinstance(values, (list, tuple)):
        candidates = list(values)
    else:
        candidates = []
    return [str(item).strip() for item in candidates if str(item).strip()][:limit]


def build_visual_brief(state: EcommerceResearchState) -> dict[str, Any]:
    query = state.get("query", "")
    review = state.get("review_result", {})
    competitor = state.get("competitor_result", {})
    score = state.get("opportunity_score", {})
    pain_points = review.get("pain_points", [])[:3]
    differentiators = _competitor_differentiation(competitor)
    return {
        "product_positioning": f"{query} product concept for {state.get('target_market', 'US')} ecommerce buyers",
        "target_customer": "buyers matching the observed trend and review pain points",
        "design_direction": ", ".join([*differentiators, *pain_points]) or score.get("recommendation", ""),
        "differentiation": differentiators,
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
    market = state.get("target_market", "US")
    pain_points = state.get("review_result", {}).get("pain_points", [])[:3]
    differentiators = _competitor_differentiation(state.get("competitor_result", {}))
    # 【正经注释】把差异化卖点 / 痛点【按 slot 轮流取用】而不是全拼成一坨塞进每个 prompt ——
    # 否则 6 个 prompt 末尾都贴同一坨 design_direction blob，出图几乎一样、且分不清 slot 用途。
    d1 = differentiators[0] if len(differentiators) > 0 else "a differentiated design"
    d2 = differentiators[1] if len(differentiators) > 1 else d1
    d3 = differentiators[2] if len(differentiators) > 2 else d2
    pp1 = pain_points[0] if len(pain_points) > 0 else "everyday convenience"
    pp2 = pain_points[1] if len(pain_points) > 1 else pp1
    reason_parts = [*differentiators, *pain_points]
    reason = " / ".join(str(item) for item in reason_parts if item) or "derived from ecommerce research evidence"
    source_refs = ["review_result.pain_points", "competitor_result.differentiation_opportunities"]
    negative = "brand logo, medical claims, exaggerated promises, watermark, distorted product, unreadable text, cluttered background"
    if kind == "listing" and slot == "main_image":
        # Amazon 主图：纯白底、单品、无文案无 logo —— 不塞卖点（主图合规要求）
        prompt = (
            f"Amazon main image of a {query}: single product centered on a pure white (#FFFFFF) background, "
            f"no props, no text, no logo, product fills about 85% of the frame. Clean even studio lighting, "
            f"accurate shape and realistic materials. Catalog-ready for the {market} marketplace."
        )
    elif kind == "listing" and slot == "infographic":
        # 卖点信息图：三个差异化卖点做成 callout
        prompt = (
            f"Amazon listing infographic for a {query}: realistic product render on a light background with "
            f"three clean benefit callouts — {d1}, {d2}, {d3}. Minimal legible English text labels with simple "
            f"icon markers, tidy layout, no brand logo, no exaggerated claims."
        )
    elif kind == "listing" and slot == "lifestyle":
        # 生活方式图：目标用户在真实场景使用，强调解决某个痛点
        prompt = (
            f"Amazon lifestyle image of a {query}: target customer using it in a believable daily scene "
            f"(commute, gym, or kitchen), natural light, premium but realistic. Emphasize portability and "
            f"that it solves: {pp1}. No text overlay, no logo."
        )
    elif slot == "detail":
        # 差异化细节微距：聚焦某个具体卖点结构
        prompt = (
            f"Macro detail close-up of the {query}'s differentiating feature: {d2}. Tight crop on a clean "
            f"white surface, raking light to reveal material and mechanism, photorealistic. No text, no logo."
        )
    elif slot == "use_case":
        # 使用场景图：真实客户在用，强调解决另一个痛点
        prompt = (
            f"Use-case concept image of a {query}: a realistic customer scenario showing it in action, "
            f"modern clean ecommerce style. Emphasize how it solves the pain point: {pp2}. No logo, no watermark."
        )
    else:
        # product_concept / appearance：产品概念 hero 图，突出首要卖点
        prompt = (
            f"Hero product concept render of a {query} for {market} ecommerce buyers: full product at a "
            f"three-quarter angle on a seamless light-gray studio background, soft directional light, premium "
            f"realistic materials. Make the key differentiator visible — {d1}. No logo, no text, no watermark."
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
