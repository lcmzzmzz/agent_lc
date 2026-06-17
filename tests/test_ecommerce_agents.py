"""EcomResearcher 7 个 Agent 的单测（注入 fake_search / fake_llm，不触网）。"""

import pytest

from multi_agents.ecommerce.agents.competitor_analyzer import run_competitor_analysis
from multi_agents.ecommerce.agents.opportunity_scorer import run_opportunity_scoring
from multi_agents.ecommerce.agents.planner import run_planner
from multi_agents.ecommerce.agents.quality_reviewer import run_quality_review
from multi_agents.ecommerce.agents.report_writer import run_report_writer
from multi_agents.ecommerce.agents.review_insight import run_review_insight
from multi_agents.ecommerce.agents.trend_researcher import run_trend_research
from multi_agents.ecommerce.state import create_initial_state


async def fake_search(query: str, max_results: int):
    return [
        {
            "title": f"Result for {query}",
            "href": f"https://example.com/{query.replace(' ', '-')}",
            "body": "Customers complain about battery life. Price is around $30. Demand is growing.",
        }
    ]


async def fake_llm(system: str, user: str) -> str:
    """返回评分 JSON 的假 LLM。"""
    return (
        '{"trend_score": 8.5, "competition_score": 5.0, "pain_point_score": 9.0, '
        '"margin_score": 7.0, "risk_score": 6.0, "reasons": ["需求旺盛", "痛点集中"]}'
    )


# ---------------------------------------------------------------------------
# Task 3: planner / trend / competitor / review
# ---------------------------------------------------------------------------


def test_run_planner_adds_query_groups():
    state = run_planner(create_initial_state("portable blender"))

    assert state["research_plan"]["trend_queries"]
    assert state["research_plan"]["competitor_queries"]
    assert state["research_plan"]["review_queries"]
    assert state["research_plan"]["scoring_dimensions"]
    assert state["audit_log"][-1]["agent"] == "ProductResearchPlannerAgent"


@pytest.mark.asyncio
async def test_run_trend_research_returns_result():
    state = run_planner(create_initial_state("portable blender"))

    updated = await run_trend_research(state, search_fn=fake_search)

    assert updated["trend_result"]["summary"]
    assert updated["trend_result"]["trend_score"] >= 0
    assert updated["trend_result"]["evidence"]
    assert updated["audit_log"][-1]["agent"] == "TrendResearchAgent"


@pytest.mark.asyncio
async def test_run_competitor_analysis_returns_result():
    state = run_planner(create_initial_state("portable blender"))

    updated = await run_competitor_analysis(state, search_fn=fake_search)

    assert updated["competitor_result"]["summary"]
    assert updated["competitor_result"]["price_range"]
    assert "$30" in updated["competitor_result"]["price_range"]
    assert updated["competitor_result"]["evidence"]


@pytest.mark.asyncio
async def test_run_review_insight_returns_pain_points():
    state = run_planner(create_initial_state("portable blender"))

    updated = await run_review_insight(state, search_fn=fake_search)

    assert updated["review_result"]["pain_points"]
    assert updated["review_result"]["pain_point_score"] >= 0


@pytest.mark.asyncio
async def test_run_trend_research_degrades_on_search_failure():
    async def failing_search(query, max_results):
        raise RuntimeError("network down")

    state = run_planner(create_initial_state("portable blender"))

    updated = await run_trend_research(state, search_fn=failing_search)

    assert updated["trend_result"]["confidence"] < 0.5
    assert updated["audit_log"][-1]["status"] == "partial"
    assert updated["errors"]


# ---------------------------------------------------------------------------
# Task 4: scoring / writer / quality
# ---------------------------------------------------------------------------


def build_ready_state():
    """构造已具备三方研究结果的 state，供 scoring/writer/quality 测试。"""
    state = create_initial_state("portable blender")
    state["trend_result"] = {
        "summary": "Demand is growing.",
        "trend_score": 7.0,
        "key_findings": ["Growing demand"],
        "evidence": [{"title": "Trend", "url": "https://example.com/trend"}],
        "confidence": 0.8,
    }
    state["competitor_result"] = {
        "summary": "Competition exists.",
        "competition_score": 6.0,
        "price_range": "$20-$60",
        "differentiation_opportunities": ["Improve battery life"],
        "evidence": [{"title": "Competitor", "url": "https://example.com/competitor"}],
        "confidence": 0.7,
    }
    state["review_result"] = {
        "summary": "Users complain about leaks.",
        "pain_points": ["Users complain about leaks."],
        "pain_point_score": 8.0,
        "opportunity_insights": ["Leak-proof design"],
        "evidence": [{"title": "Review", "url": "https://example.com/review"}],
        "confidence": 0.8,
    }
    return state


@pytest.mark.asyncio
async def test_run_opportunity_scoring_rule_mode():
    state = await run_opportunity_scoring(build_ready_state())

    assert state["opportunity_score"]["overall_score"] > 0
    assert state["opportunity_score"]["recommendation"]
    assert state["opportunity_score"]["scored_by"] == "rule"
    assert state["audit_log"][-1]["agent"] == "OpportunityScoringAgent"


@pytest.mark.asyncio
async def test_run_opportunity_scoring_uses_llm():
    state = await run_opportunity_scoring(build_ready_state(), llm_fn=fake_llm)

    score = state["opportunity_score"]
    assert score["scored_by"] == "llm"
    # fake_llm 给的 trend_score=8.5 应被采用
    assert score["trend_score"] == 8.5
    assert "需求旺盛" in score["reasons"]
    # overall 仍由加权公式重算，落在合理区间
    assert 0.0 <= score["overall_score"] <= 10.0


@pytest.mark.asyncio
async def test_run_opportunity_scoring_llm_failure_falls_back_to_rule():
    async def bad_llm(system, user):
        raise RuntimeError("llm down")

    state = await run_opportunity_scoring(build_ready_state(), llm_fn=bad_llm)

    assert state["opportunity_score"]["scored_by"] == "rule"
    assert state["audit_log"][-1]["warning"] == "llm scoring unavailable, fallback to rule"


@pytest.mark.asyncio
async def test_run_report_writer_creates_markdown():
    state = run_report_writer(await run_opportunity_scoring(build_ready_state()))

    assert "# 跨境电商选品调研报告" in state["final_report"]
    assert "市场趋势分析" in state["final_report"]
    assert "https://example.com/trend" in state["final_report"]
    assert "风险因素" in state["final_report"]


@pytest.mark.asyncio
async def test_run_quality_review_adds_quality_check():
    state = run_quality_review(
        run_report_writer(await run_opportunity_scoring(build_ready_state()))
    )

    assert "citation_coverage" in state["quality_check"]
    assert "evidence_sufficiency" in state["quality_check"]
    assert state["quality_check"]["risk_disclosure"] is True


def test_quality_review_flags_overconfident_terms():
    state = create_initial_state("portable blender")
    state["trend_result"] = {"evidence": []}
    state["competitor_result"] = {"evidence": []}
    state["review_result"] = {"evidence": []}
    state["final_report"] = "稳赚必爆，没有风险。"
    updated = run_quality_review(state)

    assert updated["quality_check"]["passed"] is False
    assert any("过度确定性" in issue for issue in updated["quality_check"]["issues"])
