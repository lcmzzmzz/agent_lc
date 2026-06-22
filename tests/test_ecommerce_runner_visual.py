import json
from pathlib import Path

import pytest

from multi_agents.ecommerce.runner import run_ecommerce_research
from multi_agents.ecommerce.tools.image_generation.base import (
    ImageGenerationRequest,
    ImageGenerationResult,
)


async def fake_search(query: str, max_results: int):
    return [
        {
            "title": f"Source for {query}",
            "href": "https://example.com/source",
            "body": "Customers complain about cleaning and leakage. Demand is growing.",
        }
    ]


class FakeImageProvider:
    async def generate(self, request: ImageGenerationRequest):
        return ImageGenerationResult(
            asset_id=request.asset_id,
            status="success",
            remote_url=f"https://example.com/{request.asset_id}.jpg",
            local_path=f"/tmp/{request.asset_id}.jpg",
            width=2048,
            height=2048,
            model=request.model,
            duration_ms=1,
            usage={"generated_images": 1, "total_tokens": 100},
            mime_type="image/jpeg",
        )


@pytest.mark.asyncio
async def test_runner_writes_visual_artifacts_when_enabled(tmp_path):
    result = await run_ecommerce_research(
        query="portable blender",
        output_dir=tmp_path,
        search_fn=fake_search,
        visual_enabled=True,
        visual_image_count=3,
        image_provider=FakeImageProvider(),
    )

    assert result["visual_result"]["status"] == "success"
    assert result["evaluation_summary"]["visual_asset_count"] == 3
    # [FIX-3] assert filename + parent dir name, not a forward-slash suffix:
    # runner stores str(Path(...)) which uses backslashes on Windows, so an
    # endswith("portable-blender-visual/visual-assets.json") would fail there.
    visual_path = Path(result["output_paths"]["visual_assets"])
    assert visual_path.name == "visual-assets.json"
    assert visual_path.parent.name == "portable-blender-visual"
    assert visual_path.exists()
    visual_payload = json.loads(visual_path.read_text(encoding="utf-8"))
    assert len(visual_payload["assets"]) == 3
    assert any(row["node"] == "visual" for row in result["agent_trace"])
    run_meta = json.loads(Path(result["output_paths"]["run"]).read_text(encoding="utf-8"))
    assert run_meta["evaluation_summary"]["visual_asset_count"] == 3


@pytest.mark.asyncio
async def test_runner_keeps_visual_skipped_when_disabled(tmp_path):
    result = await run_ecommerce_research(
        query="portable blender",
        output_dir=tmp_path,
        search_fn=fake_search,
        visual_enabled=False,
    )

    assert result["visual_result"]["status"] == "skipped"
    assert "visual_assets" not in result["output_paths"]
