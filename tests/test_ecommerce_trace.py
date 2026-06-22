import pytest

from multi_agents.ecommerce.runtime.trace_recorder import (
    emit_trace,
    finish_trace_node,
    make_run_id,
    start_trace_node,
    summarize_trace,
)
from multi_agents.ecommerce.state import create_initial_state


def test_make_run_id_is_stable_with_injected_values():
    # 1782109800123 ms -> 2026-06-22 06:30:00 UTC
    run_id = make_run_id(
        "portable blender",
        now_ms=1782109800123,
        suffix="abc123",
    )

    assert run_id == "ecom_20260622063000_portable-blender_abc123"


def test_create_initial_state_contains_trace_fields():
    state = create_initial_state("portable blender")

    assert state["run_id"].startswith("ecom_")
    assert state["agent_trace"] == []
    assert state["human_review"]["review_status"] == "pending"
    assert state["eval_result"] == {}
    assert state["mcp_context"] == {
        "enabled": False,
        "strategy": "fast",
        "tool_calls": [],
    }


def test_start_and_finish_trace_node_records_summary():
    state = create_initial_state("portable blender")

    idx = start_trace_node(
        state,
        node="trend",
        agent="TrendResearchAgent",
        input_summary={"query": "portable blender"},
    )
    record = finish_trace_node(
        state,
        idx,
        status="success",
        output_summary={
            "source_count": 2,
            "confidence": 0.7,
            "scores": {"trend_score": 6.5},
            "scored_by": "llm",
        },
        warnings=["low source count"],
    )

    assert record["run_id"] == state["run_id"]
    assert record["node"] == "trend"
    assert record["agent"] == "TrendResearchAgent"
    assert record["status"] == "success"
    assert record["duration_ms"] >= 0
    assert record["input_summary"]["query"] == "portable blender"
    assert record["output_summary"]["scores"]["trend_score"] == 6.5
    assert record["warnings"] == ["low source count"]


def test_finish_trace_node_refs_only_events_during_node():
    """[FIX-2] governance_event_refs must span only events emitted while the
    node was running, not every event accumulated before it."""
    state = create_initial_state("portable blender")
    events = state["governance"]["events"]
    events.append({"kind": "policy", "agent": "planner"})  # index 0 — before node

    idx = start_trace_node(state, node="trend", agent="TrendResearchAgent")
    events.append({"kind": "tool", "agent": "trend"})      # index 1 — during
    events.append({"kind": "failure", "agent": "trend"})   # index 2 — during
    record = finish_trace_node(state, idx, status="partial")

    assert record["governance_event_refs"] == [1, 2]
    # the internal scratch key must not leak into persisted trace
    assert "_start_event_count" not in record


@pytest.mark.asyncio
async def test_emit_trace_uses_existing_progress_callback_contract():
    events = []

    async def progress(event, payload):
        events.append((event, payload))

    record = {
        "run_id": "ecom_20260622063000_portable-blender_abc123",
        "node": "trend",
        "status": "success",
    }
    await emit_trace(progress, record)

    assert events == [("trace_node_done", record)]


@pytest.mark.asyncio
async def test_emit_trace_does_not_raise_when_progress_callback_fails():
    async def progress(event, payload):
        raise RuntimeError("socket closed")

    await emit_trace(progress, {"node": "trend", "status": "success"})


def test_summarize_trace_counts_status_and_scoring_paths():
    summary = summarize_trace(
        [
            {"status": "success", "output_summary": {"scored_by": "llm"}},
            {"status": "partial", "output_summary": {"scored_by": "rule"}},
            {"status": "failed", "output_summary": {}},
        ]
    )

    assert summary == {
        "trace_node_count": 3,
        "failed_node_count": 1,
        "partial_node_count": 1,
        "llm_scored_node_count": 1,
        "rule_scored_node_count": 1,
    }
