"""EcomResearcher runner 端到端单测（注入 fake_search，写临时目录）。"""

import json

import pytest

from multi_agents.ecommerce.runner import run_ecommerce_research, slugify


async def fake_search(query: str, max_results: int):
    return [
        {
            "title": f"Source for {query}",
            "href": f"https://example.com/{query.replace(' ', '-')}",
            "body": "Customers complain about battery life. Demand is growing. Price is around $30.",
        }
    ]


def test_slugify_handles_english_and_chinese():
    assert slugify("portable blender") == "portable-blender"
    assert slugify("便携榨汁机")  # 中文应保留为非空 slug
    assert slugify("!!!") == "ecommerce-research"


@pytest.mark.asyncio
async def test_run_ecommerce_research_writes_outputs(tmp_path):
    result = await run_ecommerce_research(
        query="portable blender",
        target_market="US",
        platforms=["amazon", "google"],
        depth="standard",
        output_dir=tmp_path,
        search_fn=fake_search,
    )

    assert result["final_report"]
    assert result["quality_check"]
    assert result["audit_log"]
    assert result["evaluation_summary"]["overall_score"] >= 0
    assert result["output_paths"]["report"].endswith("portable-blender-report.md")

    report_path = tmp_path / "portable-blender-report.md"
    audit_path = tmp_path / "portable-blender-audit.json"
    quality_path = tmp_path / "portable-blender-quality.json"
    evaluation_path = tmp_path / "portable-blender-evaluation.json"

    assert report_path.exists()
    assert audit_path.exists()
    assert quality_path.exists()
    assert evaluation_path.exists()
    assert "跨境电商选品调研报告" in report_path.read_text(encoding="utf-8")
    assert json.loads(quality_path.read_text(encoding="utf-8"))["citation_coverage"] >= 0
    # 审计日志应覆盖全部 7 个 agent
    agents_logged = {
        entry["agent"] for entry in json.loads(audit_path.read_text(encoding="utf-8"))
    }
    assert "ProductResearchPlannerAgent" in agents_logged
    assert "OpportunityScoringAgent" in agents_logged
    assert "QualityReviewerAgent" in agents_logged


@pytest.mark.asyncio
async def test_runner_degrades_when_search_returns_nothing(tmp_path):
    async def empty_search(query, max_results):
        return []

    result = await run_ecommerce_research(
        query="some niche widget",
        output_dir=tmp_path,
        search_fn=empty_search,
    )

    # 即使零数据源，也应产出报告与质检，且不抛异常
    assert result["final_report"]
    assert result["quality_check"]["passed"] is False
    assert result["quality_check"]["citation_coverage"] == 0.0
