from multi_agents.ecommerce.evaluation import build_evaluation_summary
from multi_agents.ecommerce.runtime.telemetry import (
    empty_governance_state,
    record_event,
    summarize_governance,
)
from multi_agents.ecommerce.state import create_initial_state


def test_record_event_updates_governance_summary():
    governance = empty_governance_state()

    record_event(
        governance,
        kind="fallback",
        agent="ReviewInsightAgent",
        detail="apify returned 0 reviews",
        fallback_used=True,
    )
    record_event(
        governance,
        kind="budget",
        agent="OpportunityScoringAgent",
        detail="llm budget exceeded",
        degraded_by_budget=True,
    )
    record_event(
        governance,
        kind="policy",
        agent="runner",
        detail="blocked unsafe url",
        policy_blocked=True,
    )

    summary = summarize_governance(governance)

    assert summary["failure_count"] == 0
    assert summary["fallback_count"] == 1
    assert summary["policy_block_count"] == 1
    assert summary["budget_exceeded"] is True
    assert summary["degraded_by_budget"] is True
    assert summary["retry_count"] == 0


def test_create_initial_state_contains_governance_state():
    state = create_initial_state("portable blender")

    assert "governance" in state
    assert state["governance"]["events"] == []
    assert state["governance"]["usage"]["llm_call_count"] == 0


def test_evaluation_summary_includes_governance_metrics():
    state = create_initial_state("portable blender")
    record_event(
        state["governance"],
        kind="fallback",
        agent="ReviewInsightAgent",
        detail="fallback used",
        fallback_used=True,
    )
    state["opportunity_score"] = {"overall_score": 6.5, "recommendation": "test"}
    state["quality_check"] = {"passed": True}

    summary = build_evaluation_summary(state)

    assert summary["overall_score"] == 6.5
    assert summary["fallback_count"] == 1
    assert summary["policy_block_count"] == 0
    assert summary["budget_exceeded"] is False
    assert summary["llm_call_count"] == 0
    assert summary["search_call_count"] == 0
    assert summary["scrape_call_count"] == 0
