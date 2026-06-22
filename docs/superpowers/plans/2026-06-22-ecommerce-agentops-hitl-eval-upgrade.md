# Ecommerce AgentOps HITL Eval Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a traceable, evaluable, human-reviewable EcomResearcher workflow on top of the existing `multi_agents/ecommerce` LangGraph implementation.

**Architecture:** Keep the current LangGraph node order and state-driven workflow. Add lightweight state fields, a trace recorder, file-backed run storage, batch eval utilities, static HTML review surfaces, and an optional MCP evidence adapter around the existing search function.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic, LangGraph, pytest with `pytest.mark.asyncio`, static HTML/CSS/JavaScript, existing GPT Researcher search and MCP components.

## Global Constraints

- No database, login, team permission backend, or complex audit permission model in this iteration.
- Do not replace the current static HTML ecommerce pages with a full Next.js workstation.
- Do not change the existing ecommerce LangGraph node order or core opportunity scoring weights.
- LangSmith is optional; the feature must run without LangSmith.
- MCP is optional and not the default search source; MCP failure must not block the default search chain.
- Reuse existing `EcommerceResearchState`, `runner.py`, `progress_callback`, `output_paths`, `audit_log`, and `governance`.
- Human review is run-after-review in this plan; no LangGraph interrupt/resume in this iteration.
- Use `py -m pytest ...` on this Windows workspace.
- Keep unrelated dirty worktree changes out of each task commit.

---

## File Structure

- Create `multi_agents/ecommerce/runtime/trace_recorder.py`: pure helpers for `run_id`, trace records, trace events, and trace summary stats.
- Modify `multi_agents/ecommerce/state.py`: add state fields and initialize `run_id`, `agent_trace`, `human_review`, `eval_result`, and `mcp_context`.
- Modify `multi_agents/ecommerce/graph.py`: wrap each LangGraph node with trace start/finish and emit `trace_node_done` through the existing `progress_callback`.
- Modify `multi_agents/ecommerce/evaluation.py`: include trace, human review, eval result, and MCP summary fields in `build_evaluation_summary()`.
- Modify `multi_agents/ecommerce/runner.py`: write `trace.json`, `human-review.json`, and `run.json`; add those paths to `output_paths`.
- Create `multi_agents/ecommerce/runtime/run_store.py`: load run artifacts and save human review JSON from the file-backed `outputs/ecommerce` store.
- Modify `backend/server/ecommerce_api.py`: expose trace fields in existing responses; add run lookup, human review save, and eval endpoints.
- Create `multi_agents/ecommerce/eval_runner.py`: load JSONL eval cases, evaluate one result, and batch-run cases.
- Create `multi_agents/ecommerce/eval_cases/cases.jsonl`: three golden cases for local/demo evaluation.
- Create `multi_agents/ecommerce/eval_cases/README.md`: document eval case schema and how to run it.
- Modify `scripts/export_ecommerce_demo_cases.py`: preserve new trace/eval/run links in demo manifests.
- Modify `frontend/ecommerce.html`: add run id and live trace panel.
- Create `frontend/ecommerce-review.html`: static human review page backed by the new APIs.
- Modify `frontend/ecommerce-eval.html`: display eval run metrics if present in manifest summaries.
- Create `multi_agents/ecommerce/tools/mcp_adapter.py`: normalize optional MCP results and combine them with base search results.
- Modify `multi_agents/ecommerce/tools/product_search.py`: allow MCP-normalized sources to pass through the existing source normalization path.
- Add tests:
  - `tests/test_ecommerce_trace.py`
  - `tests/test_ecommerce_api.py`
  - `tests/test_ecommerce_eval_runner.py`
  - `tests/test_ecommerce_human_review.py`
  - `tests/test_ecommerce_mcp_adapter.py`
  - Extend existing `tests/test_ecommerce_state.py`, `tests/test_ecommerce_runner.py`, `tests/test_ecommerce_evaluation.py`, `tests/test_ecommerce_graph_langgraph.py`, `tests/test_ecommerce_demo_export.py`.

---

### Task 1: State And Trace Recorder Foundation

**Files:**
- Create: `multi_agents/ecommerce/runtime/trace_recorder.py`
- Modify: `multi_agents/ecommerce/state.py`
- Test: `tests/test_ecommerce_trace.py`
- Test: `tests/test_ecommerce_state.py`

**Interfaces:**
- Consumes: existing `EcommerceResearchState` dict contract.
- Produces:
  - `make_run_id(query: str, *, now_ms: int | None = None, suffix: str | None = None) -> str`
  - `start_trace_node(state: dict[str, Any], *, node: str, agent: str, input_summary: Mapping[str, Any] | None = None) -> int`
  - `finish_trace_node(state: dict[str, Any], trace_index: int, *, status: str, output_summary: Mapping[str, Any] | None = None, warnings: Sequence[str] | None = None, error: str = "") -> dict[str, Any]`
  - `emit_trace(progress_callback: Callable[[str, dict], Awaitable[None]] | None, record: Mapping[str, Any]) -> Awaitable[None]`
  - `summarize_trace(trace: Sequence[Mapping[str, Any]]) -> dict[str, int]`
  - `create_initial_state()` now initializes `run_id`, `agent_trace`, `human_review`, `eval_result`, and `mcp_context`.

- [ ] **Step 1: Write failing trace recorder tests**

Create `tests/test_ecommerce_trace.py` with:

```python
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
```

Extend `tests/test_ecommerce_state.py`:

```python
def test_create_initial_state_includes_agentops_defaults():
    state = create_initial_state("portable blender")

    assert state["run_id"].startswith("ecom_")
    assert state["agent_trace"] == []
    assert state["human_review"]["review_status"] == "pending"
    assert state["eval_result"] == {}
    assert state["mcp_context"]["enabled"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
py -m pytest tests/test_ecommerce_trace.py tests/test_ecommerce_state.py::test_create_initial_state_includes_agentops_defaults -q
```

Expected: FAIL with import errors for `multi_agents.ecommerce.runtime.trace_recorder` and missing state keys.

- [ ] **Step 3: Implement trace recorder**

Create `multi_agents/ecommerce/runtime/trace_recorder.py`:

```python
"""Structured trace helpers for ecommerce AgentOps."""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

_SLUG_RE = re.compile(r"\W+", flags=re.UNICODE)


def _slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "ecommerce-research"


def _now_ms() -> int:
    return int(time.time() * 1000)


def make_run_id(
    query: str,
    *,
    now_ms: int | None = None,
    suffix: str | None = None,
) -> str:
    stamp_ms = _now_ms() if now_ms is None else now_ms
    stamp = datetime.fromtimestamp(stamp_ms / 1000, tz=timezone.utc).strftime(
        "%Y%m%d%H%M%S"
    )
    short = suffix or uuid.uuid4().hex[:6]
    return f"ecom_{stamp}_{_slugify(query)}_{short}"


def start_trace_node(
    state: dict[str, Any],
    *,
    node: str,
    agent: str,
    input_summary: Mapping[str, Any] | None = None,
) -> int:
    trace = state.setdefault("agent_trace", [])
    record = {
        "run_id": state.get("run_id", ""),
        "node": node,
        "agent": agent,
        "status": "running",
        "started_at_ms": _now_ms(),
        "ended_at_ms": 0,
        "duration_ms": 0,
        "input_summary": dict(input_summary or {}),
        "output_summary": {},
        "warnings": [],
        "error": "",
        "governance_event_refs": [],
    }
    trace.append(record)
    return len(trace) - 1


def finish_trace_node(
    state: dict[str, Any],
    trace_index: int,
    *,
    status: str,
    output_summary: Mapping[str, Any] | None = None,
    warnings: Sequence[str] | None = None,
    error: str = "",
) -> dict[str, Any]:
    trace = state.setdefault("agent_trace", [])
    record = trace[trace_index]
    ended_at_ms = _now_ms()
    record["status"] = status
    record["ended_at_ms"] = ended_at_ms
    record["duration_ms"] = max(0, ended_at_ms - int(record.get("started_at_ms", 0)))
    record["output_summary"] = dict(output_summary or {})
    record["warnings"] = [str(item) for item in (warnings or []) if item]
    record["error"] = str(error or "")
    event_count = len(state.get("governance", {}).get("events", []))
    record["governance_event_refs"] = list(range(event_count))
    return record


async def emit_trace(
    progress_callback: Callable[[str, dict], Awaitable[None]] | None,
    record: Mapping[str, Any],
) -> None:
    if progress_callback is None:
        return
    await progress_callback("trace_node_done", dict(record))


def summarize_trace(trace: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "trace_node_count": len(trace),
        "failed_node_count": sum(1 for row in trace if row.get("status") == "failed"),
        "partial_node_count": sum(1 for row in trace if row.get("status") == "partial"),
        "llm_scored_node_count": sum(
            1
            for row in trace
            if row.get("output_summary", {}).get("scored_by") == "llm"
        ),
        "rule_scored_node_count": sum(
            1
            for row in trace
            if row.get("output_summary", {}).get("scored_by") == "rule"
        ),
    }
```

- [ ] **Step 4: Add state fields**

Modify `multi_agents/ecommerce/state.py`:

```python
from multi_agents.ecommerce.runtime.trace_recorder import make_run_id
```

Add these fields to `EcommerceResearchState` and `EcommerceGraphState`:

```python
run_id: str
agent_trace: Annotated[list[dict[str, Any]], operator.add]
human_review: dict[str, Any]
eval_result: dict[str, Any]
mcp_context: dict[str, Any]
```

In `create_initial_state()`, add:

```python
"run_id": make_run_id(query),
"agent_trace": [],
"human_review": {"review_status": "pending"},
"eval_result": {},
"mcp_context": {"enabled": False, "strategy": "fast", "tool_calls": []},
```

Use `Annotated[list[dict[str, Any]], operator.add]` for `agent_trace` in `EcommerceGraphState` so parallel branch trace records merge like `audit_log`.

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
py -m pytest tests/test_ecommerce_trace.py tests/test_ecommerce_state.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add multi_agents/ecommerce/runtime/trace_recorder.py multi_agents/ecommerce/state.py tests/test_ecommerce_trace.py tests/test_ecommerce_state.py
git commit -m "feat(ecommerce): add agentops trace state"
```

---

### Task 2: Wire Trace Through LangGraph Nodes

**Files:**
- Modify: `multi_agents/ecommerce/graph.py`
- Test: `tests/test_ecommerce_graph_langgraph.py`
- Test: `tests/test_ecommerce_trace.py`

**Interfaces:**
- Consumes:
  - `start_trace_node(state, node, agent, input_summary) -> int`
  - `finish_trace_node(state, trace_index, status, output_summary, warnings, error) -> dict`
  - `emit_trace(progress_callback, record) -> Awaitable[None]`
- Produces:
  - `run_ecommerce_graph()` final state includes seven trace records.
  - Existing progress events still emit in the same stage order.
  - Additional `trace_node_done` events emit as each node finishes.

- [ ] **Step 1: Write failing graph trace tests**

Extend `tests/test_ecommerce_graph_langgraph.py`:

```python
@pytest.mark.asyncio
async def test_graph_records_trace_for_all_nodes(monkeypatch):
    monkeypatch.setattr(graph_mod, "run_trend_research", _ok_branch("trend_result", "TrendResearchAgent"))
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", _ok_branch("competitor_result", "CompetitorAnalysisAgent"))
    monkeypatch.setattr(graph_mod, "run_review_insight", _ok_branch("review_result", "ReviewInsightAgent"))

    state = create_initial_state("portable blender")
    final = await run_ecommerce_graph(state, search_fn=_fake_search)

    nodes = [row["node"] for row in final["agent_trace"]]
    assert nodes.count("planner") == 1
    assert nodes.count("trend") == 1
    assert nodes.count("competitor") == 1
    assert nodes.count("review") == 1
    assert nodes.count("scoring") == 1
    assert nodes.count("writer") == 1
    assert nodes.count("quality") == 1
    assert all(row["run_id"] == state["run_id"] for row in final["agent_trace"])
    assert all(row["status"] in {"success", "partial"} for row in final["agent_trace"])


@pytest.mark.asyncio
async def test_trace_node_done_events_do_not_break_stage_order(monkeypatch):
    events = []

    async def progress(event, payload):
        events.append(event)

    monkeypatch.setattr(graph_mod, "run_trend_research", _ok_branch("trend_result", "TrendResearchAgent"))
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", _ok_branch("competitor_result", "CompetitorAnalysisAgent"))
    monkeypatch.setattr(graph_mod, "run_review_insight", _ok_branch("review_result", "ReviewInsightAgent"))

    state = create_initial_state("portable blender")
    await run_ecommerce_graph(state, search_fn=_fake_search, progress_callback=progress)

    stage_events = [event for event in events if event != "trace_node_done"]
    assert stage_events == [
        "start",
        "planner_done",
        "research_running",
        "research_done",
        "scoring_done",
        "report_done",
        "quality_done",
    ]
    assert events.count("trace_node_done") == 7


@pytest.mark.asyncio
async def test_failed_research_branch_gets_partial_trace(monkeypatch):
    async def fail_trend(child, *, search_fn, llm_fn=None):
        raise RuntimeError("trend boom")

    monkeypatch.setattr(graph_mod, "run_trend_research", fail_trend)
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", _ok_branch("competitor_result", "CompetitorAnalysisAgent"))
    monkeypatch.setattr(graph_mod, "run_review_insight", _ok_branch("review_result", "ReviewInsightAgent"))

    state = create_initial_state("portable blender")
    final = await run_ecommerce_graph(state, search_fn=_fake_search)

    trend_trace = next(row for row in final["agent_trace"] if row["node"] == "trend")
    assert trend_trace["status"] == "partial"
    assert trend_trace["output_summary"]["source_count"] == 0
    assert "trend boom" in trend_trace["warnings"][0]
```

Modify existing `test_all_eight_progress_events_emitted_in_order` so it filters trace events:

```python
stage_events = [event for event in events if event != "trace_node_done"]
assert stage_events == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
py -m pytest tests/test_ecommerce_graph_langgraph.py::test_graph_records_trace_for_all_nodes tests/test_ecommerce_graph_langgraph.py::test_trace_node_done_events_do_not_break_stage_order tests/test_ecommerce_graph_langgraph.py::test_failed_research_branch_gets_partial_trace -q
```

Expected: FAIL because `agent_trace` stays empty and no `trace_node_done` events are emitted.

- [ ] **Step 3: Import trace helpers and add summary helpers**

Modify imports in `multi_agents/ecommerce/graph.py`:

```python
from multi_agents.ecommerce.runtime.trace_recorder import (
    emit_trace,
    finish_trace_node,
    start_trace_node,
)
```

Add helper functions near `_failed_child_state()`:

```python
def _score_summary(result: dict, *score_keys: str) -> dict:
    scores = {
        key: result.get(key)
        for key in score_keys
        if result.get(key) is not None
    }
    return {
        "source_count": len(result.get("evidence", [])),
        "confidence": result.get("confidence", 0.0),
        "scores": scores,
        "scored_by": result.get("scored_by", "rule"),
    }


def _planner_input_summary(s: dict) -> dict:
    return {
        "query": s.get("query"),
        "target_market": s.get("target_market"),
        "platforms": s.get("platforms", []),
        "depth": s.get("depth"),
    }


def _planner_output_summary(plan: dict) -> dict:
    return {
        "trend_query_count": len(plan.get("trend_queries", [])),
        "competitor_query_count": len(plan.get("competitor_queries", [])),
        "review_query_count": len(plan.get("review_queries", [])),
        "risk_focus_count": len(plan.get("risk_focus", [])),
    }


def _writer_output_summary(report: str) -> dict:
    return {
        "report_chars": len(report or ""),
        "section_count": (report or "").count("\n## "),
        "citation_count": (report or "").count("http"),
    }
```

- [ ] **Step 4: Wrap planner, scoring, writer, and quality nodes**

In `planner_node`, add a trace index before calling `run_planner()` and finish it before returning:

```python
trace_idx = start_trace_node(
    child,
    node="planner",
    agent="ProductResearchPlannerAgent",
    input_summary=_planner_input_summary(s),
)
out = run_planner(child)
plan = out.get("research_plan", {})
record = finish_trace_node(
    child,
    trace_idx,
    status="success",
    output_summary=_planner_output_summary(plan),
)
await emit_trace(progress_callback, record)
```

Return `agent_trace` from the node:

```python
return {
    "research_plan": plan,
    "audit_log": out["audit_log"],
    "agent_trace": child["agent_trace"],
}
```

Use the same pattern in `scoring_node`:

```python
trace_idx = start_trace_node(
    child,
    node="scoring",
    agent="OpportunityScoringAgent",
    input_summary={
        "trend_score": s.get("trend_result", {}).get("trend_score"),
        "competition_score": s.get("competitor_result", {}).get("competition_score"),
        "pain_point_score": s.get("review_result", {}).get("pain_point_score"),
    },
)
out = await run_opportunity_scoring(
    child, llm_fn=llm_fn, budget_manager=budget_manager
)
score = out["opportunity_score"]
record = finish_trace_node(
    child,
    trace_idx,
    status="success",
    output_summary={
        "source_count": score.get("evidence_score", 0),
        "confidence": out["audit_log"][-1].get("confidence", 0.0) if out["audit_log"] else 0.0,
        "scores": {
            "trend_score": score.get("trend_score"),
            "competition_score": score.get("competition_score"),
            "pain_point_score": score.get("pain_point_score"),
            "margin_score": score.get("margin_score"),
            "risk_score": score.get("risk_score"),
            "overall_score": score.get("overall_score"),
        },
        "scored_by": score.get("scored_by", "rule"),
        "recommendation": score.get("recommendation"),
    },
)
await emit_trace(progress_callback, record)
return {
    "opportunity_score": score,
    "audit_log": out["audit_log"],
    "agent_trace": child["agent_trace"],
}
```

For `writer_node`, finish with:

```python
record = finish_trace_node(
    child,
    trace_idx,
    status="success",
    output_summary=_writer_output_summary(out["final_report"]),
)
await emit_trace(progress_callback, record)
return {
    "final_report": out["final_report"],
    "audit_log": out["audit_log"],
    "agent_trace": child["agent_trace"],
}
```

For `quality_node`, finish with:

```python
quality = out["quality_check"]
record = finish_trace_node(
    child,
    trace_idx,
    status="success" if quality.get("passed") else "partial",
    output_summary={
        "passed": quality.get("passed", False),
        "citation_coverage": quality.get("citation_coverage", 0.0),
        "evidence_sufficiency": quality.get("evidence_sufficiency", 0.0),
        "issue_count": len(quality.get("issues", [])),
    },
    warnings=quality.get("issues", []),
)
await emit_trace(progress_callback, record)
return {
    "quality_check": quality,
    "audit_log": out["audit_log"],
    "agent_trace": child["agent_trace"],
}
```

- [ ] **Step 5: Wrap the shared research node**

In `_research_node`, call `start_trace_node()` immediately after `child = _fresh_child(...)`:

```python
trace_idx = start_trace_node(
    child,
    node=result_key.replace("_result", ""),
    agent=agent_name,
    input_summary={
        "query": s.get("query"),
        "target_market": s.get("target_market"),
        "plan": s.get("research_plan", {}),
    },
)
```

After `res` is available, derive status, warning, and score keys:

```python
score_keys = {
    "trend_result": ("trend_score",),
    "competitor_result": ("competition_score",),
    "review_result": ("pain_point_score",),
}.get(result_key, ())
result = res.get(result_key, {})
status = "partial" if result.get("data_failed") or result.get("error") else "success"
warnings = []
if result.get("error"):
    warnings.append(str(result["error"]))
if res.get("audit_log"):
    warning = res["audit_log"][-1].get("warning")
    if warning:
        warnings.append(str(warning))
record = finish_trace_node(
    child,
    trace_idx,
    status=status,
    output_summary=_score_summary(result, *score_keys),
    warnings=warnings,
    error=str(result.get("error", "")),
)
await emit_trace(progress_callback, record)
```

Return trace increments:

```python
return {
    result_key: res[result_key],
    "audit_log": res["audit_log"],
    "errors": res["errors"],
    "agent_trace": child["agent_trace"],
}
```

Replace temporary `print(...)` calls in touched nodes with `logger.debug(...)`:

```python
logger.debug("%s out: %s", agent_name, res)
```

- [ ] **Step 6: Run graph trace tests**

Run:

```bash
py -m pytest tests/test_ecommerce_graph_langgraph.py tests/test_ecommerce_trace.py -q
```

Expected: PASS.

- [ ] **Step 7: Run core ecommerce regression tests**

Run:

```bash
py -m pytest tests/test_ecommerce_agents.py tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_graph_langgraph.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add multi_agents/ecommerce/graph.py tests/test_ecommerce_graph_langgraph.py tests/test_ecommerce_trace.py
git commit -m "feat(ecommerce): trace langgraph nodes"
```

---

### Task 3: Persist Trace And Extend Evaluation Summary

**Files:**
- Modify: `multi_agents/ecommerce/runner.py`
- Modify: `multi_agents/ecommerce/evaluation.py`
- Test: `tests/test_ecommerce_runner.py`
- Test: `tests/test_ecommerce_evaluation.py`

**Interfaces:**
- Consumes:
  - `summarize_trace(trace) -> dict[str, int]`
  - `state["agent_trace"]`, `state["human_review"]`, `state["eval_result"]`, `state["mcp_context"]`
- Produces:
  - `outputs/ecommerce/<slug>-trace.json`
  - `outputs/ecommerce/<slug>-human-review.json`
  - `outputs/ecommerce/<slug>-run.json`
  - `output_paths["trace"]`, `output_paths["human_review"]`, `output_paths["run"]`
  - `evaluation_summary` includes run, trace, human, eval, and MCP metrics.

- [ ] **Step 1: Write failing runner persistence assertions**

Extend `tests/test_ecommerce_runner.py::test_run_ecommerce_research_writes_outputs`:

```python
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
```

- [ ] **Step 2: Write failing evaluation summary tests**

Extend `_FAKE_STATE` in `tests/test_ecommerce_evaluation.py`:

```python
    "run_id": "ecom_20260622063000_portable-blender_abc123",
    "agent_trace": [
        {"status": "success", "output_summary": {"scored_by": "llm"}},
        {"status": "partial", "output_summary": {"scored_by": "rule"}},
    ],
    "human_review": {
        "review_status": "revised",
        "evidence_labels": [
            {"label": "irrelevant"},
            {"label": "weak"},
        ],
        "score_overrides": {
            "trend_score": {"value": 6.5, "original_value": 7.4}
        },
        "report_labels": ["citation_weak"],
    },
    "eval_result": {"passed": False, "score": 0.72},
    "mcp_context": {
        "enabled": True,
        "strategy": "fast",
        "tool_calls": [{"status": "success"}, {"status": "failed"}],
    },
```

Add assertions:

```python
    assert summary["run_id"] == "ecom_20260622063000_portable-blender_abc123"
    assert summary["trace_node_count"] == 2
    assert summary["partial_node_count"] == 1
    assert summary["llm_scored_node_count"] == 1
    assert summary["rule_scored_node_count"] == 1
    assert summary["human_review_status"] == "revised"
    assert summary["human_overridden_score_count"] == 1
    assert summary["human_irrelevant_source_count"] == 1
    assert summary["human_weak_source_count"] == 1
    assert summary["human_report_label_count"] == 1
    assert summary["eval_passed"] is False
    assert summary["eval_score"] == 0.72
    assert summary["mcp_enabled"] is True
    assert summary["mcp_tool_call_count"] == 2
    assert summary["mcp_failed_tool_call_count"] == 1
```

In `test_build_evaluation_summary_handles_empty_state`, add:

```python
    assert summary["run_id"] == ""
    assert summary["trace_node_count"] == 0
    assert summary["human_review_status"] == "none"
    assert summary["human_overridden_score_count"] == 0
    assert summary["eval_passed"] is None
    assert summary["mcp_enabled"] is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
py -m pytest tests/test_ecommerce_runner.py::test_run_ecommerce_research_writes_outputs tests/test_ecommerce_evaluation.py -q
```

Expected: FAIL because new paths and summary fields are missing.

- [ ] **Step 4: Extend evaluation summary**

Modify `multi_agents/ecommerce/evaluation.py`:

```python
from multi_agents.ecommerce.runtime.trace_recorder import summarize_trace
```

Add helper functions:

```python
def _summarize_human_review(review: Mapping[str, Any] | None) -> dict[str, Any]:
    if not review:
        return {
            "human_review_status": "none",
            "human_overridden_score_count": 0,
            "human_irrelevant_source_count": 0,
            "human_weak_source_count": 0,
            "human_report_label_count": 0,
        }
    labels = review.get("evidence_labels", [])
    return {
        "human_review_status": review.get("review_status", "pending"),
        "human_overridden_score_count": len(review.get("score_overrides", {})),
        "human_irrelevant_source_count": sum(
            1 for row in labels if row.get("label") == "irrelevant"
        ),
        "human_weak_source_count": sum(
            1 for row in labels if row.get("label") == "weak"
        ),
        "human_report_label_count": len(review.get("report_labels", [])),
    }


def _summarize_eval_result(eval_result: Mapping[str, Any] | None) -> dict[str, Any]:
    if not eval_result:
        return {"eval_passed": None, "eval_score": 0.0}
    return {
        "eval_passed": eval_result.get("passed"),
        "eval_score": float(eval_result.get("score", 0.0)),
    }


def _summarize_mcp_context(mcp_context: Mapping[str, Any] | None) -> dict[str, Any]:
    if not mcp_context:
        return {
            "mcp_enabled": False,
            "mcp_tool_call_count": 0,
            "mcp_failed_tool_call_count": 0,
        }
    calls = mcp_context.get("tool_calls", [])
    return {
        "mcp_enabled": bool(mcp_context.get("enabled", False)),
        "mcp_tool_call_count": len(calls),
        "mcp_failed_tool_call_count": sum(
            1 for row in calls if row.get("status") not in {"success", "ok"}
        ),
    }
```

Before returning `summary`, update:

```python
summary["run_id"] = state.get("run_id", "")
summary.update(summarize_trace(state.get("agent_trace", [])))
summary.update(_summarize_human_review(state.get("human_review")))
summary.update(_summarize_eval_result(state.get("eval_result")))
summary.update(_summarize_mcp_context(state.get("mcp_context")))
```

- [ ] **Step 5: Persist new artifacts in runner**

Modify `multi_agents/ecommerce/runner.py`.

Add helper:

```python
def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

Create paths after existing `evaluation_path`:

```python
trace_path = output_path / f"{slug}-trace.json"
human_review_path = output_path / f"{slug}-human-review.json"
run_path = output_path / f"{slug}-run.json"
```

Replace repeated JSON writes with `_write_json(...)` and add:

```python
_write_json(trace_path, final_state.get("agent_trace", []))
_write_json(human_review_path, final_state.get("human_review", {"review_status": "pending"}))
```

After `evaluation_summary` is created and assigned:

```python
final_state["output_paths"] = {
    "report": str(report_path),
    "audit": str(audit_path),
    "quality": str(quality_path),
    "evaluation": str(evaluation_path),
    "trace": str(trace_path),
    "human_review": str(human_review_path),
    "run": str(run_path),
    "log": str(log_path),
}
run_metadata = {
    "run_id": final_state.get("run_id", ""),
    "query": final_state.get("query", ""),
    "target_market": final_state.get("target_market", ""),
    "created_at_ms": int(datetime.datetime.now().timestamp() * 1000),
    "output_paths": final_state["output_paths"],
    "evaluation_summary": evaluation_summary,
}
_write_json(run_path, run_metadata)
```

Write `evaluation_path` after the summary includes trace and human defaults:

```python
evaluation_summary = build_evaluation_summary(final_state)
final_state["evaluation_summary"] = evaluation_summary
_write_json(evaluation_path, evaluation_summary)
```

- [ ] **Step 6: Run persistence and summary tests**

Run:

```bash
py -m pytest tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py -q
```

Expected: PASS.

- [ ] **Step 7: Run regression tests**

Run:

```bash
py -m pytest tests/test_ecommerce_agents.py tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_graph_langgraph.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add multi_agents/ecommerce/runner.py multi_agents/ecommerce/evaluation.py tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py
git commit -m "feat(ecommerce): persist trace and run metadata"
```

---

### Task 4: File-Backed Run Store And Ecommerce API Extensions

**Files:**
- Create: `multi_agents/ecommerce/runtime/run_store.py`
- Modify: `backend/server/ecommerce_api.py`
- Test: `tests/test_ecommerce_api.py`
- Test: `tests/test_ecommerce_human_review.py`

**Interfaces:**
- Consumes:
  - runner-created `<slug>-run.json`, `<slug>-trace.json`, `<slug>-human-review.json`, report, audit, quality, evaluation files.
- Produces:
  - `load_run(run_id: str, *, output_dir: str | Path = "outputs/ecommerce") -> dict[str, Any]`
  - `save_human_review(run_id: str, review: Mapping[str, Any], *, output_dir: str | Path = "outputs/ecommerce") -> dict[str, Any]`
  - `EcommerceRequest` includes `mcp_enabled`, `mcp_strategy`, `mcp_configs`, `trace_enabled`.
  - `GET /api/ecommerce/runs/{run_id}`
  - `POST /api/ecommerce/runs/{run_id}/human-review`

- [ ] **Step 1: Write failing run store tests**

Create `tests/test_ecommerce_human_review.py`:

```python
import json

from multi_agents.ecommerce.runtime.run_store import load_run, save_human_review


def _write_run_fixture(root):
    run_id = "ecom_20260622063000_portable-blender_abc123"
    trace = [{"run_id": run_id, "node": "planner"}]
    review = {"review_status": "pending"}
    evaluation = {"overall_score": 6.5}
    report = "# Report"
    paths = {
        "trace": str(root / "portable-blender-trace.json"),
        "human_review": str(root / "portable-blender-human-review.json"),
        "evaluation": str(root / "portable-blender-evaluation.json"),
        "report": str(root / "portable-blender-report.md"),
    }
    (root / "portable-blender-trace.json").write_text(json.dumps(trace), encoding="utf-8")
    (root / "portable-blender-human-review.json").write_text(json.dumps(review), encoding="utf-8")
    (root / "portable-blender-evaluation.json").write_text(json.dumps(evaluation), encoding="utf-8")
    (root / "portable-blender-report.md").write_text(report, encoding="utf-8")
    (root / "portable-blender-run.json").write_text(
        json.dumps({"run_id": run_id, "output_paths": paths}),
        encoding="utf-8",
    )
    return run_id


def test_load_run_reads_file_backed_artifacts(tmp_path):
    run_id = _write_run_fixture(tmp_path)

    payload = load_run(run_id, output_dir=tmp_path)

    assert payload["run_id"] == run_id
    assert payload["agent_trace"][0]["node"] == "planner"
    assert payload["human_review"]["review_status"] == "pending"
    assert payload["evaluation_summary"]["overall_score"] == 6.5
    assert payload["report"] == "# Report"


def test_save_human_review_updates_review_file(tmp_path):
    run_id = _write_run_fixture(tmp_path)
    review = {
        "review_status": "revised",
        "score_overrides": {
            "trend_score": {
                "value": 6.5,
                "original_value": 7.4,
                "reason": "mixed evidence",
            }
        },
    }

    saved = save_human_review(run_id, review, output_dir=tmp_path)
    loaded = load_run(run_id, output_dir=tmp_path)

    assert saved["review_status"] == "revised"
    assert loaded["human_review"]["score_overrides"]["trend_score"]["value"] == 6.5
```

- [ ] **Step 2: Write failing API tests**

Create `tests/test_ecommerce_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.server import ecommerce_api


def _client():
    app = FastAPI()
    app.include_router(ecommerce_api.router)
    return TestClient(app)


def test_ecommerce_research_response_includes_agentops_fields(monkeypatch):
    async def fake_run(**kwargs):
        return {
            "run_id": "ecom_20260622063000_portable-blender_abc123",
            "query": kwargs["query"],
            "target_market": kwargs["target_market"],
            "trend_result": {},
            "competitor_result": {},
            "review_result": {},
            "opportunity_score": {},
            "quality_check": {},
            "audit_log": [],
            "agent_trace": [{"node": "planner"}],
            "evaluation_summary": {"trace_node_count": 1},
            "human_review": {"review_status": "pending"},
            "eval_result": {},
            "mcp_context": {"enabled": False, "strategy": "fast", "tool_calls": []},
            "final_report": "# Report",
            "output_paths": {"trace": "trace.json"},
        }

    monkeypatch.setattr(ecommerce_api, "run_ecommerce_research", fake_run)

    response = _client().post(
        "/api/ecommerce/research",
        json={
            "query": "portable blender",
            "mcp_enabled": True,
            "mcp_strategy": "fast",
            "mcp_configs": [{"name": "demo"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "ecom_20260622063000_portable-blender_abc123"
    assert data["agent_trace"][0]["node"] == "planner"
    assert data["evaluation_summary"]["trace_node_count"] == 1
    assert data["human_review"]["review_status"] == "pending"


def test_human_review_endpoint_saves_payload(monkeypatch, tmp_path):
    run_id = "ecom_20260622063000_portable-blender_abc123"
    saved_payloads = []

    def fake_save(target_run_id, review, output_dir="outputs/ecommerce"):
        saved_payloads.append((target_run_id, review))
        return {"review_status": review["review_status"]}

    monkeypatch.setattr(ecommerce_api, "save_human_review", fake_save)

    response = _client().post(
        f"/api/ecommerce/runs/{run_id}/human-review",
        json={"review_status": "revised", "report_labels": ["citation_weak"]},
    )

    assert response.status_code == 200
    assert response.json()["human_review"]["review_status"] == "revised"
    assert saved_payloads[0][0] == run_id
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
py -m pytest tests/test_ecommerce_human_review.py tests/test_ecommerce_api.py -q
```

Expected: FAIL because `run_store.py` and new API fields/endpoints are missing.

- [ ] **Step 4: Implement run store**

Create `multi_agents/ecommerce/runtime/run_store.py`:

```python
"""File-backed run artifact store for ecommerce research."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _find_run_file(run_id: str, output_dir: str | Path) -> Path:
    root = Path(output_dir)
    for path in root.glob("*-run.json"):
        data = _read_json(path, {})
        if data.get("run_id") == run_id:
            return path
    raise FileNotFoundError(f"ecommerce run not found: {run_id}")


def _read_text(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_run(
    run_id: str,
    *,
    output_dir: str | Path = "outputs/ecommerce",
) -> dict[str, Any]:
    run_path = _find_run_file(run_id, output_dir)
    metadata = _read_json(run_path, {})
    paths = metadata.get("output_paths", {})
    return {
        **metadata,
        "agent_trace": _read_json(Path(paths.get("trace", "")), []),
        "human_review": _read_json(
            Path(paths.get("human_review", "")),
            {"review_status": "pending"},
        ),
        "evaluation_summary": _read_json(
            Path(paths.get("evaluation", "")),
            metadata.get("evaluation_summary", {}),
        ),
        "report": _read_text(paths.get("report")),
    }


def save_human_review(
    run_id: str,
    review: Mapping[str, Any],
    *,
    output_dir: str | Path = "outputs/ecommerce",
) -> dict[str, Any]:
    metadata = _read_json(_find_run_file(run_id, output_dir), {})
    paths = metadata.get("output_paths", {})
    review_path = Path(paths.get("human_review", ""))
    if not review_path:
        raise FileNotFoundError(f"human review path missing for run: {run_id}")
    payload = dict(review)
    payload.setdefault("review_status", "pending")
    review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
```

- [ ] **Step 5: Extend API request and response**

Modify `backend/server/ecommerce_api.py`.

Add imports:

```python
from typing import Any

from multi_agents.ecommerce.runtime.run_store import load_run, save_human_review
```

Extend request model:

```python
class EcommerceRequest(BaseModel):
    query: str
    target_market: str = "US"
    platforms: list[str] = ["amazon", "google"]
    depth: str = "standard"
    use_llm: bool = True
    mcp_enabled: bool = False
    mcp_strategy: str = "fast"
    mcp_configs: list[dict[str, Any]] = []
    trace_enabled: bool = True
```

Extend `_summarize()`:

```python
"run_id": result.get("run_id"),
"agent_trace": result.get("agent_trace", []),
"evaluation_summary": result.get("evaluation_summary", {}),
"human_review": result.get("human_review", {}),
"eval_result": result.get("eval_result", {}),
"mcp_context": result.get("mcp_context", {}),
```

Pass fields through to runner:

```python
mcp_enabled=req.mcp_enabled,
mcp_strategy=req.mcp_strategy,
mcp_configs=req.mcp_configs,
trace_enabled=req.trace_enabled,
```

Add endpoints:

```python
@router.get("/api/ecommerce/runs/{run_id}")
async def ecommerce_run(run_id: str) -> dict:
    return load_run(run_id)


@router.post("/api/ecommerce/runs/{run_id}/human-review")
async def ecommerce_human_review(run_id: str, review: dict[str, Any]) -> dict:
    saved = save_human_review(run_id, review)
    return {"run_id": run_id, "human_review": saved}
```

If runner does not yet accept MCP fields, add them to `run_ecommerce_research()` signature with defaults and store them in `state["mcp_context"]`. Full MCP search behavior is implemented in Task 8.

- [ ] **Step 6: Run API and run store tests**

Run:

```bash
py -m pytest tests/test_ecommerce_human_review.py tests/test_ecommerce_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Run API import smoke test**

Run:

```bash
py - <<'PY'
from backend.server.ecommerce_api import router
print(len(router.routes))
PY
```

Expected output: an integer greater than `3`.

- [ ] **Step 8: Commit**

```bash
git add backend/server/ecommerce_api.py multi_agents/ecommerce/runtime/run_store.py tests/test_ecommerce_api.py tests/test_ecommerce_human_review.py
git commit -m "feat(ecommerce): add run store and review api"
```

---

### Task 5: Golden Case Evaluation Runner

**Files:**
- Create: `multi_agents/ecommerce/eval_runner.py`
- Create: `multi_agents/ecommerce/eval_cases/cases.jsonl`
- Create: `multi_agents/ecommerce/eval_cases/README.md`
- Modify: `backend/server/ecommerce_api.py`
- Test: `tests/test_ecommerce_eval_runner.py`

**Interfaces:**
- Consumes:
  - `run_ecommerce_research(**case_input) -> EcommerceResearchState`
  - case JSONL schema from spec.
- Produces:
  - `load_eval_cases(path: str | Path) -> list[dict[str, Any]]`
  - `evaluate_case_result(case: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]`
  - `run_eval_cases(cases_path: str | Path, *, output_dir: str | Path, run_fn=run_ecommerce_research) -> dict[str, Any]`
  - `POST /api/ecommerce/eval/run`
  - `GET /api/ecommerce/eval/runs/{eval_run_id}`

- [ ] **Step 1: Write failing eval runner tests**

Create `tests/test_ecommerce_eval_runner.py`:

```python
import json

import pytest

from multi_agents.ecommerce.eval_runner import (
    evaluate_case_result,
    load_eval_cases,
    run_eval_cases,
)


def _case():
    return {
        "case_id": "portable-blender-us-standard",
        "query": "portable blender",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "standard",
        "expected": {
            "trend_range": [6.0, 8.0],
            "competition_range": [4.0, 7.0],
            "pain_point_range": [6.0, 9.0],
            "overall_range": [5.5, 8.0],
            "must_have_risks": ["battery", "leakage"],
            "must_have_pain_points": ["cleaning"],
            "min_citations": 2,
            "max_fallback_count": 1,
        },
    }


def _result():
    return {
        "run_id": "ecom_20260622063000_portable-blender_abc123",
        "trend_result": {"trend_score": 6.8},
        "competitor_result": {"competition_score": 5.8},
        "review_result": {
            "pain_point_score": 7.4,
            "pain_points": ["cleaning is difficult", "battery life is short"],
        },
        "opportunity_score": {"overall_score": 6.6},
        "quality_check": {"passed": True, "citation_coverage": 0.8},
        "evaluation_summary": {"fallback_count": 0, "evidence_count": 4},
        "final_report": "Battery risk and leakage risk are cited.\nhttps://a\nhttps://b",
    }


def test_load_eval_cases_reads_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(_case()) + "\n", encoding="utf-8")

    cases = load_eval_cases(path)

    assert cases[0]["case_id"] == "portable-blender-us-standard"


def test_evaluate_case_result_passes_matching_result():
    eval_result = evaluate_case_result(_case(), _result())

    assert eval_result["case_id"] == "portable-blender-us-standard"
    assert eval_result["passed"] is True
    assert eval_result["checks"]["trend_range"] is True
    assert eval_result["checks"]["must_have_risks"] is True
    assert eval_result["checks"]["min_citations"] is True
    assert eval_result["score"] >= 0.8


def test_evaluate_case_result_reports_failed_checks():
    result = _result()
    result["trend_result"]["trend_score"] = 9.5
    result["final_report"] = "No risk citations"

    eval_result = evaluate_case_result(_case(), result)

    assert eval_result["passed"] is False
    assert eval_result["checks"]["trend_range"] is False
    assert eval_result["checks"]["must_have_risks"] is False


@pytest.mark.asyncio
async def test_run_eval_cases_writes_summary(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_case()) + "\n", encoding="utf-8")

    async def fake_run(**kwargs):
        return _result()

    summary = await run_eval_cases(cases_path, output_dir=tmp_path, run_fn=fake_run)

    assert summary["total_cases"] == 1
    assert summary["passed_cases"] == 1
    assert summary["pass_rate"] == 1.0
    assert (tmp_path / summary["eval_run_id"] / "summary.json").exists()
    assert (tmp_path / summary["eval_run_id"] / "case-index.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
py -m pytest tests/test_ecommerce_eval_runner.py -q
```

Expected: FAIL because `eval_runner.py` is missing.

- [ ] **Step 3: Implement eval runner**

Create `multi_agents/ecommerce/eval_runner.py`:

```python
"""Batch evaluation utilities for ecommerce golden cases."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from multi_agents.ecommerce.runner import run_ecommerce_research

RunFn = Callable[..., Awaitable[dict[str, Any]]]


def load_eval_cases(path: str | Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            cases.append(json.loads(text))
    return cases


def _in_range(value: float, bounds: list[float]) -> bool:
    return float(bounds[0]) <= float(value) <= float(bounds[1])


def _contains_all(text: str, required: list[str]) -> bool:
    lowered = text.lower()
    return all(item.lower() in lowered for item in required)


def _citation_count(report: str) -> int:
    return report.count("http://") + report.count("https://")


def evaluate_case_result(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    expected = case.get("expected", {})
    report = str(result.get("final_report", ""))
    review_text = " ".join(result.get("review_result", {}).get("pain_points", []))
    checks = {
        "trend_range": _in_range(
            result.get("trend_result", {}).get("trend_score", 0.0),
            expected.get("trend_range", [0.0, 10.0]),
        ),
        "competition_range": _in_range(
            result.get("competitor_result", {}).get("competition_score", 0.0),
            expected.get("competition_range", [0.0, 10.0]),
        ),
        "pain_point_range": _in_range(
            result.get("review_result", {}).get("pain_point_score", 0.0),
            expected.get("pain_point_range", [0.0, 10.0]),
        ),
        "overall_range": _in_range(
            result.get("opportunity_score", {}).get("overall_score", 0.0),
            expected.get("overall_range", [0.0, 10.0]),
        ),
        "must_have_risks": _contains_all(
            report,
            expected.get("must_have_risks", []),
        ),
        "must_have_pain_points": _contains_all(
            f"{review_text}\n{report}",
            expected.get("must_have_pain_points", []),
        ),
        "min_citations": _citation_count(report) >= int(expected.get("min_citations", 0)),
        "max_fallback_count": int(
            result.get("evaluation_summary", {}).get("fallback_count", 0)
        )
        <= int(expected.get("max_fallback_count", 99)),
        "quality_passed": bool(result.get("quality_check", {}).get("passed", False)),
    }
    passed_count = sum(1 for passed in checks.values() if passed)
    score = round(passed_count / len(checks), 2) if checks else 0.0
    return {
        "case_id": case.get("case_id", ""),
        "run_id": result.get("run_id", ""),
        "passed": all(checks.values()),
        "score": score,
        "checks": checks,
    }


async def run_eval_cases(
    cases_path: str | Path,
    *,
    output_dir: str | Path = "outputs/ecommerce/eval-runs",
    run_fn: RunFn = run_ecommerce_research,
) -> dict[str, Any]:
    cases = load_eval_cases(cases_path)
    eval_run_id = f"eval_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    target = Path(output_dir) / eval_run_id
    target.mkdir(parents=True, exist_ok=True)
    case_results: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for case in cases:
        result = await run_fn(
            query=case["query"],
            target_market=case.get("target_market", "US"),
            platforms=case.get("platforms", ["amazon", "google"]),
            depth=case.get("depth", "standard"),
        )
        eval_result = evaluate_case_result(case, result)
        result["eval_result"] = eval_result
        case_results.append(eval_result)
        manifest.append(
            {
                "case_id": case.get("case_id", ""),
                "title": case.get("case_id", ""),
                "query": case.get("query", ""),
                "summary": {
                    **result.get("evaluation_summary", {}),
                    "eval_passed": eval_result["passed"],
                    "eval_score": eval_result["score"],
                },
            }
        )
    passed_cases = sum(1 for row in case_results if row["passed"])
    summary = {
        "eval_run_id": eval_run_id,
        "total_cases": len(case_results),
        "passed_cases": passed_cases,
        "pass_rate": round(passed_cases / len(case_results), 2) if case_results else 0.0,
        "cases": case_results,
    }
    (target / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "cases.json").write_text(
        json.dumps(case_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "case-index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
```

- [ ] **Step 4: Add eval cases**

Create `multi_agents/ecommerce/eval_cases/cases.jsonl`:

```json
{"case_id":"portable-blender-us-standard","query":"portable blender","target_market":"US","platforms":["amazon","google"],"depth":"standard","expected":{"trend_range":[5.0,8.5],"competition_range":[3.0,8.0],"pain_point_range":[5.0,9.0],"overall_range":[4.5,8.5],"must_have_risks":["battery","leakage"],"must_have_pain_points":["battery"],"min_citations":2,"max_fallback_count":2}}
{"case_id":"pet-water-fountain-us-standard","query":"pet water fountain","target_market":"US","platforms":["amazon","google"],"depth":"standard","expected":{"trend_range":[4.0,8.5],"competition_range":[3.0,8.0],"pain_point_range":[5.0,9.0],"overall_range":[4.0,8.5],"must_have_risks":["leak","clean"],"must_have_pain_points":["clean"],"min_citations":2,"max_fallback_count":2}}
{"case_id":"car-toy-us-fast","query":"car toy","target_market":"US","platforms":["amazon","google"],"depth":"fast","expected":{"trend_range":[3.0,8.5],"competition_range":[2.0,8.0],"pain_point_range":[3.0,9.0],"overall_range":[3.0,8.5],"must_have_risks":["safety"],"must_have_pain_points":["quality"],"min_citations":1,"max_fallback_count":3}}
```

Create `multi_agents/ecommerce/eval_cases/README.md`:

```markdown
# Ecommerce Eval Cases

Each line in `cases.jsonl` is one golden case for the ecommerce research workflow.

Required fields:

- `case_id`: stable identifier.
- `query`: product/category query.
- `target_market`: market code accepted by `validate_research_request()`.
- `platforms`: search platforms.
- `depth`: `fast`, `standard`, or `deep`.
- `expected`: score ranges and coverage constraints.

Run from the project root with:

```bash
py -m pytest tests/test_ecommerce_eval_runner.py -q
```

Programmatic usage:

```python
from multi_agents.ecommerce.eval_runner import run_eval_cases
```
```

- [ ] **Step 5: Add eval API endpoints**

Modify `backend/server/ecommerce_api.py`:

```python
from pathlib import Path

from multi_agents.ecommerce.eval_runner import run_eval_cases
```

Add request model:

```python
class EcommerceEvalRequest(BaseModel):
    cases_path: str = "multi_agents/ecommerce/eval_cases/cases.jsonl"
    output_dir: str = "outputs/ecommerce/eval-runs"
```

Add endpoints:

```python
@router.post("/api/ecommerce/eval/run")
async def ecommerce_eval_run(req: EcommerceEvalRequest) -> dict:
    return await run_eval_cases(req.cases_path, output_dir=req.output_dir)


@router.get("/api/ecommerce/eval/runs/{eval_run_id}")
async def ecommerce_eval_result(eval_run_id: str) -> dict:
    path = Path("outputs/ecommerce/eval-runs") / eval_run_id / "summary.json"
    if not path.exists():
        raise FileNotFoundError(f"eval run not found: {eval_run_id}")
    return json.loads(path.read_text(encoding="utf-8"))
```

Add `import json` if not already present.

- [ ] **Step 6: Run eval runner tests**

Run:

```bash
py -m pytest tests/test_ecommerce_eval_runner.py tests/test_ecommerce_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add multi_agents/ecommerce/eval_runner.py multi_agents/ecommerce/eval_cases/cases.jsonl multi_agents/ecommerce/eval_cases/README.md backend/server/ecommerce_api.py tests/test_ecommerce_eval_runner.py tests/test_ecommerce_api.py
git commit -m "feat(ecommerce): add golden case eval runner"
```

---

### Task 6: Static Frontend Trace And Human Review Workstation

**Files:**
- Modify: `frontend/ecommerce.html`
- Create: `frontend/ecommerce-review.html`
- Modify: `frontend/ecommerce-eval.html`
- Test: manual browser smoke test with local FastAPI server.

**Interfaces:**
- Consumes:
  - Existing `WS /ws/ecommerce`
  - `trace_node_done` events
  - `GET /api/ecommerce/runs/{run_id}`
  - `POST /api/ecommerce/runs/{run_id}/human-review`
- Produces:
  - Main ecommerce page displays run id and trace rows.
  - Review page can load a run, collect labels/overrides, and save review JSON.
  - Eval page displays `eval_passed`, `eval_score`, `human_overridden_score_count`, `mcp_tool_call_count` when present.

- [ ] **Step 1: Add run id and trace panel to main page markup**

Modify `frontend/ecommerce.html`. Add this card after the progress card:

```html
<div class="card hidden" id="traceCard">
  <strong>AgentOps Trace</strong>
  <span class="pill" id="runIdPill">run_id: -</span>
  <div style="overflow-x:auto; margin-top:10px;">
    <table>
      <thead>
        <tr>
          <th>Node</th>
          <th>Status</th>
          <th>Duration</th>
          <th>Sources</th>
          <th>Score</th>
          <th>By</th>
          <th>Warnings</th>
        </tr>
      </thead>
      <tbody id="traceBody"></tbody>
    </table>
  </div>
</div>
```

Add CSS:

```css
.trace-warn { color: var(--warn); max-width: 260px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
```

- [ ] **Step 2: Add trace rendering JavaScript**

In `frontend/ecommerce.html`, add helpers before the WebSocket click handler:

```javascript
function firstScore(scores){
  if(!scores) return "-";
  const keys = Object.keys(scores);
  if(keys.length === 0) return "-";
  const v = scores[keys[0]];
  return v == null ? "-" : Number(v).toFixed(1);
}

function renderTraceRow(row){
  $("traceCard").classList.remove("hidden");
  if(row.run_id) $("runIdPill").textContent = "run_id: " + row.run_id;
  const out = row.output_summary || {};
  const warnings = (row.warnings || []).join("; ");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td>${row.node || "-"}</td>
    <td class="${row.status === "success" ? "ok" : "warn"}">${row.status || "-"}</td>
    <td>${row.duration_ms == null ? "-" : row.duration_ms}</td>
    <td>${out.source_count == null ? "-" : out.source_count}</td>
    <td>${firstScore(out.scores)}</td>
    <td>${out.scored_by || "-"}</td>
    <td class="trace-warn" title="${warnings}">${warnings || "-"}</td>
  `;
  $("traceBody").appendChild(tr);
}
```

In `resetUI()` add:

```javascript
$("traceCard").classList.add("hidden");
$("traceBody").innerHTML = "";
$("runIdPill").textContent = "run_id: -";
```

In `ws.onmessage`, before the final `else` branch:

```javascript
} else if(event === "trace_node_done"){
  renderTraceRow(data);
```

In the `done` branch:

```javascript
if(data.run_id) $("runIdPill").textContent = "run_id: " + data.run_id;
(data.agent_trace || []).forEach(row => {
  if(!Array.from($("traceBody").children).some(tr => tr.children[0].textContent === row.node)){
    renderTraceRow(row);
  }
});
```

- [ ] **Step 3: Create human review page**

Create `frontend/ecommerce-review.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>EcomResearcher Human Review</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --border:#334155; --txt:#e2e8f0; --mut:#94a3b8; --acc:#38bdf8; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt); font-family:system-ui,-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif; line-height:1.6; }
  header { padding:20px 28px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  main { max-width:1180px; margin:0 auto; padding:24px; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:18px; margin-bottom:18px; }
  .row { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; }
  .row > div { flex:1; min-width:180px; }
  label { display:block; font-size:13px; color:var(--mut); margin:8px 0 4px; }
  input, select, textarea { width:100%; padding:10px 12px; background:#0b1220; border:1px solid var(--border); border-radius:8px; color:var(--txt); font-size:14px; }
  textarea { min-height:90px; }
  button { background:var(--acc); color:#06283d; border:none; border-radius:8px; padding:10px 16px; font-weight:600; cursor:pointer; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:7px 8px; border-bottom:1px solid var(--border); text-align:left; vertical-align:top; }
  th { color:var(--mut); font-weight:500; }
  .pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; background:#0b1220; border:1px solid var(--border); }
  .hidden { display:none; }
  .ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }
</style>
</head>
<body>
<header>
  <h1>EcomResearcher Review</h1>
  <span class="pill" id="status">idle</span>
</header>
<main>
  <div class="card">
    <div class="row">
      <div>
        <label>Backend Host</label>
        <input id="host" value="localhost:8000" />
      </div>
      <div>
        <label>Run ID</label>
        <input id="runId" aria-label="Run ID" />
      </div>
      <div style="flex:0 0 auto;">
        <button id="loadBtn">Load</button>
      </div>
    </div>
  </div>

  <div class="card hidden" id="reviewCard">
    <h2>Plan Review</h2>
    <textarea id="planComment" aria-label="Plan review comment"></textarea>

    <h2>Evidence Labels</h2>
    <table>
      <thead><tr><th>URL</th><th>Label</th><th>Reason</th></tr></thead>
      <tbody id="evidenceBody"></tbody>
    </table>

    <h2>Score Overrides</h2>
    <div class="row">
      <div><label>Trend</label><input id="trendOverride" type="number" min="0" max="10" step="0.1" /></div>
      <div><label>Competition</label><input id="competitionOverride" type="number" min="0" max="10" step="0.1" /></div>
      <div><label>Pain Point</label><input id="painOverride" type="number" min="0" max="10" step="0.1" /></div>
    </div>
    <label>Override Reason</label>
    <textarea id="overrideReason"></textarea>

    <h2>Report Labels</h2>
    <div class="row">
      <label><input type="checkbox" class="reportLabel" value="citation_weak" /> citation_weak</label>
      <label><input type="checkbox" class="reportLabel" value="risk_missing" /> risk_missing</label>
      <label><input type="checkbox" class="reportLabel" value="overconfident" /> overconfident</label>
      <label><input type="checkbox" class="reportLabel" value="evidence_mismatch" /> evidence_mismatch</label>
    </div>
    <button id="saveBtn">Save Review</button>
  </div>
</main>
<script>
const $ = (id) => document.getElementById(id);
let currentRun = null;

function apiBase(){
  return `http://${$("host").value.trim()}`;
}

function setStatus(text, cls=""){
  const e = $("status");
  e.textContent = text;
  e.className = "pill " + cls;
}

function allSources(run){
  const buckets = ["trend_result", "competitor_result", "review_result"];
  return buckets.flatMap(key => (run[key] && run[key].evidence) || []);
}

function renderEvidence(run){
  $("evidenceBody").innerHTML = allSources(run).map((src, idx) => `
    <tr data-url="${src.url || src.href || ""}">
      <td>${src.url || src.href || src.title || "-"}</td>
      <td>
        <select class="sourceLabel">
          <option value="relevant">relevant</option>
          <option value="weak">weak</option>
          <option value="irrelevant">irrelevant</option>
          <option value="duplicate">duplicate</option>
        </select>
      </td>
      <td><input class="sourceReason" aria-label="Evidence label reason" /></td>
    </tr>
  `).join("");
}

function collectReview(){
  const labels = Array.from(document.querySelectorAll("#evidenceBody tr")).map(row => ({
    url: row.dataset.url,
    label: row.querySelector(".sourceLabel").value,
    reason: row.querySelector(".sourceReason").value.trim(),
  }));
  const score_overrides = {};
  const reason = $("overrideReason").value.trim();
  [["trend_score", "trendOverride"], ["competition_score", "competitionOverride"], ["pain_point_score", "painOverride"]].forEach(([key, id]) => {
    const raw = $(id).value;
    if(raw !== ""){
      score_overrides[key] = { value: Number(raw), reason };
    }
  });
  return {
    review_status: "revised",
    reviewer: "local_user",
    plan_review: { status: "reviewed", comment: $("planComment").value.trim() },
    evidence_labels: labels,
    score_overrides,
    report_labels: Array.from(document.querySelectorAll(".reportLabel:checked")).map(x => x.value),
  };
}

$("loadBtn").onclick = async () => {
  setStatus("loading", "warn");
  const res = await fetch(`${apiBase()}/api/ecommerce/runs/${$("runId").value.trim()}`);
  if(!res.ok){ setStatus(`load failed ${res.status}`, "bad"); return; }
  currentRun = await res.json();
  renderEvidence(currentRun);
  $("reviewCard").classList.remove("hidden");
  setStatus("loaded", "ok");
};

$("saveBtn").onclick = async () => {
  setStatus("saving", "warn");
  const res = await fetch(`${apiBase()}/api/ecommerce/runs/${$("runId").value.trim()}/human-review`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(collectReview()),
  });
  setStatus(res.ok ? "saved" : `save failed ${res.status}`, res.ok ? "ok" : "bad");
};
</script>
</body>
</html>
```

- [ ] **Step 4: Extend eval dashboard columns**

Modify `frontend/ecommerce-eval.html` table header to add:

```html
<th class="num">Eval</th>
<th class="num">Human</th>
<th class="num">MCP</th>
```

In each success row, add cells:

```javascript
<td class="num">${s.eval_passed == null ? "-" : (s.eval_passed ? "PASS" : "FAIL")} ${s.eval_score == null ? "" : Number(s.eval_score).toFixed(2)}</td>
<td class="num">${s.human_overridden_score_count == null ? "-" : s.human_overridden_score_count}</td>
<td class="num">${s.mcp_tool_call_count == null ? "-" : s.mcp_tool_call_count}</td>
```

In each error row, add three `-` cells before the Quality cell.

- [ ] **Step 5: Run backend server for manual smoke**

Run:

```bash
py -m uvicorn main:app --reload
```

Expected: server starts on `http://127.0.0.1:8000`.

- [ ] **Step 6: Manually verify pages**

Open:

```text
http://localhost:8000/site/ecommerce.html
http://localhost:8000/site/ecommerce-review.html
http://localhost:8000/site/ecommerce-eval.html
```

Expected:

- Main page can start a run and displays trace rows.
- Review page can load the run id from the main page and save a review.
- Eval page still loads existing manifest; new columns show `-` when fields are absent.

- [ ] **Step 7: Commit**

```bash
git add frontend/ecommerce.html frontend/ecommerce-review.html frontend/ecommerce-eval.html
git commit -m "feat(ecommerce): add trace and review static pages"
```

---

### Task 7: Demo Export Manifest Keeps New AgentOps Fields

**Files:**
- Modify: `scripts/export_ecommerce_demo_cases.py`
- Test: `tests/test_ecommerce_demo_export.py`

**Interfaces:**
- Consumes:
  - runner `output_paths` with `trace`, `human_review`, and `run`.
  - evaluation summary fields from Task 3.
- Produces:
  - demo manifest entries include artifact links for trace, human review, and run metadata.
  - summary fields remain pass-through.

- [ ] **Step 1: Write failing demo export test**

Extend `tests/test_ecommerce_demo_export.py`:

```python
def test_success_entry_includes_agentops_artifact_links():
    case = {
        "slug": "portable-blender",
        "title": "Portable Blender",
        "query": "portable blender",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "standard",
    }
    summary = {
        "overall_score": 6.5,
        "trace_node_count": 7,
        "human_overridden_score_count": 1,
        "mcp_tool_call_count": 0,
    }

    entry = _build_success_entry(case, summary)

    assert entry["trace"].endswith("portable-blender/trace.json")
    assert entry["human_review"].endswith("portable-blender/human-review.json")
    assert entry["run"].endswith("portable-blender/run.json")
    assert entry["summary"]["trace_node_count"] == 7
    assert entry["summary"]["human_overridden_score_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
py -m pytest tests/test_ecommerce_demo_export.py::test_success_entry_includes_agentops_artifact_links -q
```

Expected: FAIL because manifest links are missing.

- [ ] **Step 3: Update success entry builder**

Modify `_build_success_entry()` in `scripts/export_ecommerce_demo_cases.py` so the returned dict includes:

```python
"trace": f"/outputs/ecommerce/demo-cases/{slug}/trace.json",
"human_review": f"/outputs/ecommerce/demo-cases/{slug}/human-review.json",
"run": f"/outputs/ecommerce/demo-cases/{slug}/run.json",
```

When copying artifacts from a run directory into a case directory, add:

```python
("trace", "trace.json"),
("human_review", "human-review.json"),
("run", "run.json"),
```

Use the existing copy helper and skip missing optional files by checking `Path.exists()` before copying.

- [ ] **Step 4: Run demo export tests**

Run:

```bash
py -m pytest tests/test_ecommerce_demo_export.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/export_ecommerce_demo_cases.py tests/test_ecommerce_demo_export.py
git commit -m "feat(ecommerce): export agentops demo artifacts"
```

---

### Task 8: Optional MCP Evidence Adapter

**Files:**
- Create: `multi_agents/ecommerce/tools/mcp_adapter.py`
- Modify: `multi_agents/ecommerce/runner.py`
- Modify: `backend/server/ecommerce_api.py`
- Modify: `multi_agents/ecommerce/tools/product_search.py`
- Test: `tests/test_ecommerce_mcp_adapter.py`
- Test: `tests/test_ecommerce_runner.py`

**Interfaces:**
- Consumes:
  - `SearchFn(query: str, max_results: int) -> Awaitable[list[dict[str, Any]]]`
  - optional MCP search callable for tests and future real MCP wiring.
- Produces:
  - `normalize_mcp_result(raw: Mapping[str, Any]) -> dict[str, Any]`
  - `make_mcp_augmented_search_fn(base_search_fn, *, mcp_enabled, mcp_configs, mcp_strategy, governance, mcp_context, mcp_search_fn=None) -> SearchFn`
  - `run_ecommerce_research(..., mcp_enabled=False, mcp_strategy="fast", mcp_configs=None, mcp_search_fn=None)` uses augmented search when enabled.

- [ ] **Step 1: Write failing MCP adapter tests**

Create `tests/test_ecommerce_mcp_adapter.py`:

```python
import pytest

from multi_agents.ecommerce.runtime.telemetry import empty_governance_state, summarize_governance
from multi_agents.ecommerce.tools.mcp_adapter import (
    make_mcp_augmented_search_fn,
    normalize_mcp_result,
)


def test_normalize_mcp_result_maps_to_ecommerce_source_shape():
    raw = {
        "title": "MCP result",
        "url": "https://example.com/mcp",
        "content": "battery leakage complaints",
        "tool_name": "search",
        "server_name": "demo",
    }

    source = normalize_mcp_result(raw)

    assert source["title"] == "MCP result"
    assert source["href"] == "https://example.com/mcp"
    assert source["body"] == "battery leakage complaints"
    assert source["source_type"] == "mcp"
    assert source["tool_name"] == "search"
    assert source["server_name"] == "demo"


@pytest.mark.asyncio
async def test_mcp_augmented_search_combines_base_and_mcp_results():
    governance = empty_governance_state()
    mcp_context = {"enabled": True, "strategy": "fast", "tool_calls": []}

    async def base_search(query, max_results):
        return [{"title": "Base", "href": "https://example.com/base", "body": "base"}]

    async def mcp_search(query, max_results, mcp_configs, mcp_strategy):
        return [{"title": "MCP", "url": "https://example.com/mcp", "content": "mcp"}]

    search = make_mcp_augmented_search_fn(
        base_search,
        mcp_enabled=True,
        mcp_configs=[{"name": "demo"}],
        mcp_strategy="fast",
        governance=governance,
        mcp_context=mcp_context,
        mcp_search_fn=mcp_search,
    )

    results = await search("portable blender", 5)

    assert [row["title"] for row in results] == ["Base", "MCP"]
    assert summarize_governance(governance)["external_api_call_count"] == 1
    assert mcp_context["tool_calls"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_mcp_failure_returns_base_results_and_records_failure():
    governance = empty_governance_state()
    mcp_context = {"enabled": True, "strategy": "fast", "tool_calls": []}

    async def base_search(query, max_results):
        return [{"title": "Base", "href": "https://example.com/base", "body": "base"}]

    async def mcp_search(query, max_results, mcp_configs, mcp_strategy):
        raise RuntimeError("mcp down")

    search = make_mcp_augmented_search_fn(
        base_search,
        mcp_enabled=True,
        mcp_configs=[{"name": "demo"}],
        mcp_strategy="fast",
        governance=governance,
        mcp_context=mcp_context,
        mcp_search_fn=mcp_search,
    )

    results = await search("portable blender", 5)

    assert results == [{"title": "Base", "href": "https://example.com/base", "body": "base"}]
    assert summarize_governance(governance)["failure_count"] == 1
    assert mcp_context["tool_calls"][0]["status"] == "failed"
```

- [ ] **Step 2: Add runner test for MCP context**

Extend `tests/test_ecommerce_runner.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
py -m pytest tests/test_ecommerce_mcp_adapter.py tests/test_ecommerce_runner.py::test_runner_records_mcp_context_when_enabled -q
```

Expected: FAIL because `mcp_adapter.py` and runner MCP args are missing.

- [ ] **Step 4: Implement MCP adapter**

Create `multi_agents/ecommerce/tools/mcp_adapter.py`:

```python
"""Optional MCP evidence adapter for ecommerce search."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from multi_agents.ecommerce.runtime.telemetry import increment_usage, record_event
from multi_agents.ecommerce.tools.product_search import SearchFn

McpSearchFn = Callable[
    [str, int, list[dict[str, Any]], str],
    Awaitable[list[dict[str, Any]]],
]


def normalize_mcp_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": str(raw.get("title") or raw.get("name") or "MCP result"),
        "href": str(raw.get("href") or raw.get("url") or ""),
        "body": str(raw.get("body") or raw.get("content") or raw.get("snippet") or ""),
        "source_type": "mcp",
        "tool_name": str(raw.get("tool_name") or raw.get("tool") or ""),
        "server_name": str(raw.get("server_name") or raw.get("server") or ""),
    }


async def _empty_mcp_search(
    query: str,
    max_results: int,
    mcp_configs: list[dict[str, Any]],
    mcp_strategy: str,
) -> list[dict[str, Any]]:
    return []


def make_mcp_augmented_search_fn(
    base_search_fn: SearchFn,
    *,
    mcp_enabled: bool,
    mcp_configs: list[dict[str, Any]] | None,
    mcp_strategy: str,
    governance: dict[str, Any],
    mcp_context: dict[str, Any],
    mcp_search_fn: McpSearchFn | None = None,
) -> SearchFn:
    configs = mcp_configs or []
    mcp_context["enabled"] = bool(mcp_enabled)
    mcp_context["strategy"] = mcp_strategy
    mcp_context.setdefault("tool_calls", [])
    selected_mcp_search = mcp_search_fn or _empty_mcp_search

    async def search(query: str, max_results: int) -> list[dict[str, Any]]:
        base_results = await base_search_fn(query, max_results)
        if not mcp_enabled or not configs:
            return base_results
        try:
            increment_usage(governance, "external_api_call_count", 1)
            raw_results = await selected_mcp_search(
                query,
                max_results,
                configs,
                mcp_strategy,
            )
            normalized = [normalize_mcp_result(row) for row in raw_results]
            mcp_context["tool_calls"].append(
                {
                    "server": ",".join(str(c.get("name", "mcp")) for c in configs),
                    "tool": "search",
                    "query": query,
                    "status": "success",
                    "result_count": len(normalized),
                }
            )
            record_event(
                governance,
                kind="tool",
                agent="MCPSearchAdapter",
                detail=f"mcp search returned {len(normalized)} results",
            )
            return [*base_results, *normalized][:max_results]
        except Exception as exc:
            mcp_context["tool_calls"].append(
                {
                    "server": ",".join(str(c.get("name", "mcp")) for c in configs),
                    "tool": "search",
                    "query": query,
                    "status": "failed",
                    "result_count": 0,
                    "error": str(exc),
                }
            )
            record_event(
                governance,
                kind="failure",
                agent="MCPSearchAdapter",
                detail="mcp search failed",
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )
            return base_results

    return search
```

- [ ] **Step 5: Wire adapter into runner**

Modify `multi_agents/ecommerce/runner.py`.

Add import:

```python
from multi_agents.ecommerce.tools.mcp_adapter import McpSearchFn, make_mcp_augmented_search_fn
```

Extend `run_ecommerce_research()` signature:

```python
mcp_enabled: bool = False,
mcp_strategy: str = "fast",
mcp_configs: list[dict[str, Any]] | None = None,
mcp_search_fn: McpSearchFn | None = None,
trace_enabled: bool = True,
```

After `state = create_initial_state(...)`, set:

```python
state["mcp_context"] = {
    "enabled": bool(mcp_enabled),
    "strategy": mcp_strategy,
    "tool_calls": [],
}
```

After `resolved_search_fn = _resolve_search_fn(search_fn)`, wrap it:

```python
resolved_search_fn = make_mcp_augmented_search_fn(
    resolved_search_fn,
    mcp_enabled=mcp_enabled,
    mcp_configs=mcp_configs or [],
    mcp_strategy=mcp_strategy,
    governance=state["governance"],
    mcp_context=state["mcp_context"],
    mcp_search_fn=mcp_search_fn,
)
```

Keep `trace_enabled` accepted for API compatibility. If `trace_enabled` is `False`, leave trace recorder code in graph active for internal consistency; the API can choose not to display it. Do not remove trace records from state.

- [ ] **Step 6: Preserve MCP source fields through normalization**

If `multi_agents/ecommerce/tools/product_search.py` currently drops unknown fields, update the source normalization step so `tool_name` and `server_name` survive:

```python
if raw.get("source_type") == "mcp":
    normalized["source_type"] = "mcp"
    normalized["tool_name"] = raw.get("tool_name", "")
    normalized["server_name"] = raw.get("server_name", "")
```

Keep existing `title`, `href`/`url`, `body`/`snippet` behavior intact.

- [ ] **Step 7: Ensure API passes MCP fields**

Task 4 added request fields. Confirm `backend/server/ecommerce_api.py` passes:

```python
mcp_enabled=req.mcp_enabled,
mcp_strategy=req.mcp_strategy,
mcp_configs=req.mcp_configs,
trace_enabled=req.trace_enabled,
```

to `run_ecommerce_research()`.

- [ ] **Step 8: Run MCP tests**

Run:

```bash
py -m pytest tests/test_ecommerce_mcp_adapter.py tests/test_ecommerce_runner.py::test_runner_records_mcp_context_when_enabled -q
```

Expected: PASS.

- [ ] **Step 9: Run full ecommerce regression**

Run:

```bash
py -m pytest tests/test_ecommerce_agents.py tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_graph_langgraph.py tests/test_ecommerce_governance.py tests/test_ecommerce_tools.py tests/test_ecommerce_mcp_adapter.py tests/test_ecommerce_eval_runner.py tests/test_ecommerce_api.py tests/test_ecommerce_human_review.py tests/test_ecommerce_demo_export.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add multi_agents/ecommerce/tools/mcp_adapter.py multi_agents/ecommerce/tools/product_search.py multi_agents/ecommerce/runner.py backend/server/ecommerce_api.py tests/test_ecommerce_mcp_adapter.py tests/test_ecommerce_runner.py
git commit -m "feat(ecommerce): add optional mcp evidence adapter"
```

---

## Final Verification

- [ ] Run all ecommerce tests:

```bash
py -m pytest tests/test_ecommerce_agents.py tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_graph_langgraph.py tests/test_ecommerce_governance.py tests/test_ecommerce_tools.py tests/test_ecommerce_state.py tests/test_ecommerce_trace.py tests/test_ecommerce_api.py tests/test_ecommerce_eval_runner.py tests/test_ecommerce_human_review.py tests/test_ecommerce_mcp_adapter.py tests/test_ecommerce_demo_export.py -q
```

Expected: PASS.

- [ ] Run one file-backed no-network smoke with fake search:

```bash
py -m pytest tests/test_ecommerce_runner.py::test_run_ecommerce_research_writes_outputs -q
```

Expected: PASS and temporary output directory contains report, audit, quality, evaluation, trace, human review, and run metadata files.

- [ ] Start API server:

```bash
py -m uvicorn main:app --reload
```

Expected: server starts and ecommerce pages are reachable under `/site/`.

- [ ] Manual UI smoke:

```text
http://localhost:8000/site/ecommerce.html
http://localhost:8000/site/ecommerce-review.html
http://localhost:8000/site/ecommerce-eval.html
```

Expected:

- Main page shows `run_id` and trace rows.
- Review page saves human review payload.
- Eval page remains backward compatible with old manifests and displays new fields when present.
