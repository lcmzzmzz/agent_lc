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


async def fake_llm_text(system: str, user: str) -> str:
    """返回中文总结文本的假 LLM（给 trend/competitor summary 用）。"""
    return "便携榨汁机在北美市场近年需求上升，夏季与健身场景拉动明显，整体呈稳定增长态势。"


async def fake_trend_llm_json(system: str, user: str) -> str:
    return (
        '{"summary":"\\u4fbf\\u643a\\u69a8\\u6c41\\u673a demand is growing.",'
        '"trend_score":8.0,"confidence":0.74,'
        '"key_findings":["demand is growing"],"negative_signals":[],'
        '"scoring_rationale":"LLM scored from source content."}'
    )


async def fake_competitor_llm_json(system: str, user: str) -> str:
    return (
        '{"summary":"\\u4fbf\\u643a\\u69a8\\u6c41\\u673a competitor demand is growing.",'
        '"competition_score":6.5,"confidence":0.73,'
        '"competitors":[{"name":"Example Brand","positioning":"mid market"}],'
        '"competitive_signals":["public search results mention competitors"],'
        '"entry_barriers":["price competition"],'
        '"differentiation_opportunities":["improve battery life"],'
        '"scoring_rationale":"LLM scored competitor entry ease from source content."}'
    )


async def string_score_llm(system: str, user: str) -> str:
    """模拟模型把数字包成字符串返回。"""
    return (
        '{"trend_score": "8.5", "competition_score": "5", "pain_point_score": "9", '
        '"margin_score": "7", "risk_score": "6", "reasons": ["数字字符串"]}'
    )


async def partial_bad_score_llm(system: str, user: str) -> str:
    """模拟部分字段不可转数字，应该回退到规则基线字段。"""
    return (
        '{"trend_score": null, "competition_score": "bad", "pain_point_score": 9, '
        '"margin_score": "", "risk_score": 6, "reasons": ["部分字段异常"]}'
    )


def test_content_scoring_helpers_coerce_scores_and_lists():
    from multi_agents.ecommerce.agents.content_scoring import (
        coerce_confidence,
        coerce_score,
        coerce_string_list,
        source_count_confidence,
    )

    data = {"score": "8.7", "confidence": "0.95", "items": ["a", "", 3]}

    assert coerce_score(data, "score", 5.0) == 8.7
    assert coerce_score({"score": "bad"}, "score", 5.0) == 5.0
    assert coerce_confidence(data, 0.4) == 0.9
    assert coerce_confidence({"confidence": "bad"}, 0.4) == 0.4
    assert coerce_string_list(data["items"], limit=3) == ["a", "3"]
    assert source_count_confidence(6) == 0.9


def test_content_scoring_helpers_format_sources_for_prompt():
    from multi_agents.ecommerce.agents.content_scoring import format_sources_for_prompt

    text = format_sources_for_prompt(
        [
            {
                "title": "Market report",
                "url": "https://example.com/report",
                "snippet": "Demand is growing",
                "content": "More context",
            }
        ],
        limit=1,
        max_chars=200,
    )

    assert "Market report" in text
    assert "Demand is growing" in text
    assert "https://example.com/report" in text


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
    assert updated["trend_result"]["summary_source"] == "template"
    assert updated["trend_result"]["trend_score"] >= 0
    assert updated["trend_result"]["evidence"]
    assert updated["audit_log"][-1]["agent"] == "TrendResearchAgent"


@pytest.mark.asyncio
async def test_run_trend_research_summary_uses_llm():
    state = run_planner(create_initial_state("portable blender"))
    updated = await run_trend_research(
        state, search_fn=fake_search, llm_fn=fake_trend_llm_json
    )
    assert updated["trend_result"]["summary_source"] == "llm"
    assert "便携榨汁机" in updated["trend_result"]["summary"]


@pytest.mark.asyncio
async def test_run_trend_research_uses_llm_json_score_for_negative_sources():
    async def negative_search(query: str, max_results: int):
        return [
            {
                "title": f"Weak demand {query}",
                "href": f"https://example.com/weak-{query.replace(' ', '-')}",
                "body": "Retailers report slowing demand and negative consumer interest.",
            }
        ]

    async def trend_llm(system: str, user: str) -> str:
        return (
            '{"summary":"公开资料显示需求走弱。","trend_score":2.5,'
            '"confidence":0.72,"key_findings":["需求走弱"],'
            '"negative_signals":["负面报道较多"],'
            '"scoring_rationale":"来源内容主要显示需求下降。"}'
        )

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_trend_research(state, search_fn=negative_search, llm_fn=trend_llm)

    result = updated["trend_result"]
    assert result["scored_by"] == "llm"
    assert result["summary_source"] == "llm"
    assert result["trend_score"] == 2.5
    assert result["confidence"] == 0.72
    assert result["negative_signals"] == ["负面报道较多"]


@pytest.mark.asyncio
async def test_run_trend_research_invalid_llm_json_marks_rule_fallback():
    async def bad_json_llm(system: str, user: str) -> str:
        return "not json"

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_trend_research(state, search_fn=fake_search, llm_fn=bad_json_llm)

    result = updated["trend_result"]
    assert result["scored_by"] == "rule"
    assert result["summary_source"] == "template"
    assert result["trend_score"] == 7.0
    assert "fallback" in result["scoring_rationale"]


@pytest.mark.asyncio
async def test_run_competitor_analysis_summary_uses_llm():
    state = run_planner(create_initial_state("portable blender"))
    updated = await run_competitor_analysis(
        state, search_fn=fake_search, llm_fn=fake_competitor_llm_json
    )
    assert updated["competitor_result"]["summary_source"] == "llm"
    assert "便携榨汁机" in updated["competitor_result"]["summary"]


@pytest.mark.asyncio
async def test_run_competitor_analysis_returns_result():
    state = run_planner(create_initial_state("portable blender"))

    updated = await run_competitor_analysis(state, search_fn=fake_search)

    assert updated["competitor_result"]["summary"]
    assert updated["competitor_result"]["price_range"]
    assert "$30" in updated["competitor_result"]["price_range"]
    assert updated["competitor_result"]["evidence"]


@pytest.mark.asyncio
async def test_run_competitor_analysis_llm_lowers_score_for_strong_incumbents():
    async def competitor_llm(system: str, user: str) -> str:
        return (
            '{"summary":"头部品牌强，价格竞争明显。","competition_score":2.0,'
            '"confidence":0.7,'
            '"competitors":[{"name":"Dominant Brand","positioning":"头部品牌"}],'
            '"competitive_signals":["头部品牌占据主要曝光"],'
            '"entry_barriers":["价格战明显"],'
            '"differentiation_opportunities":["避开低价同质化"],'
            '"scoring_rationale":"强势竞品和价格压缩使进入难度较高。"}'
        )

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_competitor_analysis(state, search_fn=fake_search, llm_fn=competitor_llm)

    result = updated["competitor_result"]
    assert result["scored_by"] == "llm"
    assert result["competition_score"] == 2.0
    assert result["entry_barriers"] == ["价格战明显"]
    assert result["competitors"][0]["name"] == "Dominant Brand"


@pytest.mark.asyncio
async def test_run_competitor_analysis_invalid_llm_json_marks_rule_fallback():
    async def bad_json_llm(system: str, user: str) -> str:
        return "not json"

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_competitor_analysis(state, search_fn=fake_search, llm_fn=bad_json_llm)

    result = updated["competitor_result"]
    assert result["scored_by"] == "rule"
    assert result["competition_score"] == 6.0
    assert "fallback" in result["scoring_rationale"]


@pytest.mark.asyncio
async def test_run_review_insight_returns_pain_points():
    state = run_planner(create_initial_state("portable blender"))

    updated = await run_review_insight(state, search_fn=fake_search)

    assert updated["review_result"]["pain_points"]
    assert updated["review_result"]["pain_point_score"] >= 0


@pytest.mark.asyncio
async def test_run_review_insight_translates_to_chinese_with_llm():
    async def zh_llm(system, user):
        return '{"pain_points": ["电池续航差", "清洗麻烦", "漏水"]}'

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_review_insight(state, search_fn=fake_search, llm_fn=zh_llm)

    assert updated["review_result"]["pain_points_language"] == "zh"
    assert "电池续航差" in updated["review_result"]["pain_points"]


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
async def test_run_opportunity_scoring_accepts_string_scores():
    state = await run_opportunity_scoring(build_ready_state(), llm_fn=string_score_llm)

    score = state["opportunity_score"]
    assert score["scored_by"] == "llm"
    assert score["trend_score"] == 8.5
    assert score["competition_score"] == 5.0


@pytest.mark.asyncio
async def test_run_opportunity_scoring_ignores_bad_llm_score_fields():
    state = await run_opportunity_scoring(
        build_ready_state(), llm_fn=partial_bad_score_llm
    )

    score = state["opportunity_score"]
    assert score["scored_by"] == "llm"
    assert score["trend_score"] == 7.0
    assert score["competition_score"] == 6.0
    assert score["pain_point_score"] == 9.0
    assert score["margin_score"] == 6.0


@pytest.mark.asyncio
async def test_run_opportunity_scoring_llm_failure_falls_back_to_rule():
    async def bad_llm(system, user):
        raise RuntimeError("llm down")

    state = await run_opportunity_scoring(build_ready_state(), llm_fn=bad_llm)

    assert state["opportunity_score"]["scored_by"] == "rule"
    assert state["audit_log"][-1]["warning"] == "llm scoring unavailable, fallback to rule"


@pytest.mark.asyncio
async def test_opportunity_scoring_confidence_discounted_when_rule_fallback():
    """LLM 降级到规则时，audit confidence 打折（让评估页能看出评分质量降级）。"""
    rule_state = await run_opportunity_scoring(build_ready_state())  # 无 llm_fn → rule
    llm_state = await run_opportunity_scoring(build_ready_state(), llm_fn=fake_llm)

    rule_conf = rule_state["audit_log"][-1]["confidence"]
    llm_conf = llm_state["audit_log"][-1]["confidence"]
    # 同 evidence 下 base 一致：rule 的 confidence = llm 的 0.8 倍
    assert rule_conf < llm_conf
    assert rule_conf == round(llm_conf * 0.8, 2)


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


@pytest.mark.asyncio
async def test_opportunity_scoring_skips_llm_when_budget_exhausted():
    from multi_agents.ecommerce.runtime.budget_manager import BudgetConfig, BudgetManager
    from multi_agents.ecommerce.runtime.telemetry import empty_governance_state

    state = build_ready_state()
    state["governance"] = empty_governance_state()
    budget = BudgetManager(state["governance"], BudgetConfig(max_llm_calls=0))
    called = False

    async def llm_should_not_run(system, user):
        nonlocal called
        called = True
        return '{"trend_score":10}'

    updated = await run_opportunity_scoring(
        state,
        llm_fn=llm_should_not_run,
        budget_manager=budget,
    )

    assert called is False
    assert updated["opportunity_score"]["scored_by"] == "rule"
    assert updated["governance"]["budget_exceeded"] is True
