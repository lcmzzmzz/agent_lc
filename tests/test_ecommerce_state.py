"""EcomResearcher 状态、配置与评分 schema 的单测。"""

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.schemas.scoring import (
    calculate_overall_score,
    clamp_score,
)
from multi_agents.ecommerce.state import create_initial_state


def test_create_initial_state_uses_defaults():
    state = create_initial_state(query="portable blender")

    assert state["query"] == "portable blender"
    assert state["target_market"] == "US"
    assert state["platforms"] == ["amazon", "google"]
    assert state["depth"] == "standard"
    assert state["research_plan"] == {}
    assert state["audit_log"] == []
    assert state["errors"] == []


def test_create_initial_state_respects_overrides():
    state = create_initial_state(
        query="pet water fountain",
        target_market="DE",
        platforms=["amazon"],
        depth="fast",
    )

    assert state["target_market"] == "DE"
    assert state["platforms"] == ["amazon"]
    assert state["depth"] == "fast"


def test_get_depth_config_returns_standard_limits():
    config = get_depth_config("standard")

    assert config["max_sources_per_agent"] == 6
    assert config["max_queries_per_agent"] == 4
    assert config["enable_quality_review"] is True


def test_get_depth_config_falls_back_to_standard():
    assert get_depth_config("unknown") == get_depth_config("standard")


def test_get_depth_config_returns_copy():
    cfg = get_depth_config("standard")
    cfg["max_sources_per_agent"] = 999
    assert get_depth_config("standard")["max_sources_per_agent"] == 6


def test_clamp_score_keeps_score_between_zero_and_ten():
    assert clamp_score(-1) == 0.0
    assert clamp_score(11) == 10.0
    assert clamp_score(7.25) == 7.25


def test_calculate_overall_score_uses_weighted_average():
    score = calculate_overall_score(
        trend_score=8,
        competition_score=6,
        pain_point_score=7,
        margin_score=6,
        risk_score=5,
        evidence_score=8,
    )

    assert 6.0 <= score <= 8.0


def test_calculate_overall_score_respects_clamp():
    score = calculate_overall_score(
        trend_score=100,  # 超出 10 会被 clamp
        competition_score=-5,
        pain_point_score=0,
        margin_score=10,
        risk_score=10,
        evidence_score=10,
    )

    assert 0.0 <= score <= 10.0


def test_create_initial_state_includes_agentops_defaults():
    state = create_initial_state("portable blender")

    assert state["run_id"].startswith("ecom_")
    assert state["agent_trace"] == []
    assert state["human_review"]["review_status"] == "pending"
    assert state["eval_result"] == {}
    assert state["mcp_context"]["enabled"] is False
