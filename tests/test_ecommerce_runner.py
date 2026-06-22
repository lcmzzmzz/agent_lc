"""EcomResearcher runner 端到端单测（注入 fake_search，写临时目录）。"""

import json

import pytest

import multi_agents.ecommerce.graph as graph_mod
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

    assert result["run_id"].startswith("ecom_")
    assert result["agent_trace"]
    assert result["output_paths"]["trace"].endswith("portable-blender-trace.json")
    assert result["output_paths"]["human_review"].endswith("portable-blender-human-review.json")
    assert result["output_paths"]["run"].endswith("portable-blender-run.json")

    trace_path = tmp_path / "portable-blender-trace.json"
    human_review_path = tmp_path / "portable-blender-human-review.json"
    run_path = tmp_path / "portable-blender-run.json"

    assert trace_path.exists()
    assert human_review_path.exists()
    assert run_path.exists()
    assert json.loads(trace_path.read_text(encoding="utf-8"))[0]["run_id"] == result["run_id"]
    assert json.loads(human_review_path.read_text(encoding="utf-8"))["review_status"] == "pending"
    run_meta = json.loads(run_path.read_text(encoding="utf-8"))
    assert run_meta["run_id"] == result["run_id"]
    assert run_meta["output_paths"]["trace"].endswith("portable-blender-trace.json")


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


@pytest.mark.asyncio
async def test_runner_rejects_invalid_depth_before_search(tmp_path):
    called = False

    async def fake_search(query, max_results):
        nonlocal called
        called = True
        return []

    with pytest.raises(ValueError) as exc:
        await run_ecommerce_research(
            query="portable blender",
            depth="extreme",
            output_dir=tmp_path,
            search_fn=fake_search,
        )

    assert "depth" in str(exc.value)
    assert called is False


@pytest.mark.asyncio
async def test_graph_records_failure_when_parallel_agent_raises(monkeypatch):
    from multi_agents.ecommerce.graph import run_ecommerce_graph
    from multi_agents.ecommerce.runtime.telemetry import summarize_governance
    from multi_agents.ecommerce.state import create_initial_state

    async def failing_trend(state, *, search_fn, llm_fn=None):
        raise RuntimeError("trend exploded")

    async def ok_competitor(state, *, search_fn, llm_fn=None):
        state["competitor_result"] = {"evidence": [], "confidence": 0.0}
        state["audit_log"].append(
            {
                "agent": "CompetitorAnalyzerAgent",
                "status": "partial",
                "duration_ms": 0,
                "confidence": 0.0,
            }
        )
        return state

    async def ok_review(state, *, search_fn, llm_fn=None, budget_manager=None):
        state["review_result"] = {"evidence": [], "confidence": 0.0}
        state["audit_log"].append(
            {
                "agent": "ReviewInsightAgent",
                "status": "partial",
                "duration_ms": 0,
                "confidence": 0.0,
            }
        )
        return state

    monkeypatch.setattr(graph_mod, "run_trend_research", failing_trend)
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", ok_competitor)
    monkeypatch.setattr(graph_mod, "run_review_insight", ok_review)

    async def fake_search(query, max_results):
        return []

    state = create_initial_state("portable blender")
    updated = await run_ecommerce_graph(state, search_fn=fake_search)

    summary = summarize_governance(updated["governance"])
    assert summary["failure_count"] == 1
    assert any(err["agent"] == "TrendResearchAgent" for err in updated["errors"])
    assert updated["trend_result"]["summary"] == ""


@pytest.mark.asyncio
async def test_runner_records_mcp_context_when_enabled(tmp_path):
    async def mcp_search(query, max_results, mcp_configs, mcp_strategy):
        return [{"title": "MCP", "url": "https://example.com/mcp", "content": "mcp content"}]

    result = await run_ecommerce_research(
        query="portable blender",
        output_dir=tmp_path,
        search_fn=fake_search,
        mcp_enabled=True,
        mcp_strategy="fast",
        mcp_configs=[{"name": "demo"}],
        mcp_search_fn=mcp_search,
    )

    assert result["mcp_context"]["enabled"] is True
    assert result["mcp_context"]["tool_calls"]
    assert result["evaluation_summary"]["mcp_enabled"] is True
