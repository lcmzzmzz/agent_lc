from pathlib import Path

import pytest

from multi_agents.ecommerce.agents.visual_concept import (
    build_visual_prompts,
    run_visual_concept_agent,
)
from multi_agents.ecommerce.state import create_initial_state
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)


def fake_state():
    state = create_initial_state("portable blender")
    state["trend_result"] = {
        "summary": "Demand is growing among commuters and fitness users.",
        "trend_score": 7.1,
        "key_findings": ["portable blending demand is rising"],
    }
    state["competitor_result"] = {
        "summary": "Most competitors look similar and compete on price.",
        "gaps": ["easy-clean blade", "leak-proof cap"],
    }
    state["review_result"] = {
        "pain_points": ["cleaning is difficult", "battery life is short", "leaks in bags"],
        "pain_point_score": 7.6,
    }
    state["opportunity_score"] = {
        "overall_score": 6.8,
        "recommendation": "test with differentiated easy-clean design",
        "risks": ["battery safety claims"],
    }
    return state


def test_build_visual_prompts_selects_slots_by_count():
    state = fake_state()

    one = build_visual_prompts(state, image_count=1)
    three = build_visual_prompts(state, image_count=3)
    six = build_visual_prompts(state, image_count=6)

    assert [(row["kind"], row["slot"]) for row in one] == [("listing", "main_image")]
    assert [(row["kind"], row["slot"]) for row in three] == [
        ("product_concept", "appearance"),
        ("listing", "main_image"),
        ("listing", "lifestyle"),
    ]
    assert len(six) == 6
    assert six[0]["asset_id"] == "visual_product_01"
    assert six[-1]["asset_id"] == "visual_listing_03"
    assert "portable blender" in six[0]["prompt"].lower()
    assert "logo" in six[0]["negative_prompt"].lower()


class SuccessProvider:
    async def generate(self, request: ImageGenerationRequest):
        return ImageGenerationResult(
            asset_id=request.asset_id,
            status="success",
            remote_url=f"https://example.com/{request.asset_id}.jpg",
            local_path=f"/tmp/{request.asset_id}.jpg",
            width=2048,
            height=2048,
            model=request.model,
            duration_ms=10,
            usage={"generated_images": 1, "total_tokens": 100},
            mime_type="image/jpeg",
        )


class FailingProvider:
    async def generate(self, request: ImageGenerationRequest):
        return ImageGenerationResult(
            asset_id=request.asset_id,
            status="failed",
            model=request.model,
            duration_ms=5,
            warning="provider down",
        )


class ExplodingProvider:
    async def generate(self, request: ImageGenerationRequest):
        raise RuntimeError("ARK_API_KEY=secret-value provider down")


@pytest.mark.asyncio
async def test_run_visual_concept_agent_generates_assets_and_trace(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=SuccessProvider(),
        visual_enabled=True,
        image_count=3,
        output_dir=tmp_path,
    )

    visual = updated["visual_result"]
    assert visual["enabled"] is True
    assert visual["status"] == "success"
    assert len(visual["prompts"]) == 3
    assert len(visual["assets"]) == 3
    assert visual["usage"]["generated_images"] == 3
    assert visual["usage"]["total_tokens"] == 300
    trace = updated["agent_trace"][-1]
    assert trace["node"] == "visual"
    assert trace["status"] == "success"
    assert trace["output_summary"]["generated_image_count"] == 3


@pytest.mark.asyncio
async def test_run_visual_concept_agent_emits_trace_event(tmp_path):
    state = fake_state()
    events = []

    async def progress(event, payload):
        events.append((event, payload))

    await run_visual_concept_agent(
        state,
        image_provider=SuccessProvider(),
        visual_enabled=True,
        image_count=1,
        output_dir=tmp_path,
        progress_callback=progress,
    )

    assert events[-1][0] == "trace_node_done"
    assert events[-1][1]["node"] == "visual"
    assert events[-1][1]["status"] == "success"


@pytest.mark.asyncio
async def test_run_visual_concept_agent_degrades_to_prompt_only_on_failure(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=FailingProvider(),
        visual_enabled=True,
        image_count=1,
        output_dir=tmp_path,
    )

    visual = updated["visual_result"]
    assert visual["status"] == "failed"
    assert len(visual["prompts"]) == 1
    assert visual["assets"][0]["status"] == "failed"
    assert visual["assets"][0]["prompt"]
    assert visual["warnings"] == ["provider down"]


@pytest.mark.asyncio
async def test_run_visual_concept_agent_catches_provider_exception(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=ExplodingProvider(),
        visual_enabled=True,
        image_count=1,
        output_dir=tmp_path,
    )

    visual = updated["visual_result"]
    assert visual["status"] == "failed"
    assert visual["assets"][0]["status"] == "failed"
    assert "secret-value" not in visual["assets"][0]["warning"]
    assert "ARK_API_KEY=[REDACTED]" in visual["assets"][0]["warning"]


@pytest.mark.asyncio
async def test_run_visual_concept_agent_skips_when_disabled(tmp_path):
    state = fake_state()

    updated = await run_visual_concept_agent(
        state,
        image_provider=SuccessProvider(),
        visual_enabled=False,
        image_count=3,
        output_dir=tmp_path,
    )

    assert updated["visual_result"]["status"] == "skipped"
    assert updated["visual_result"]["prompts"] == []
