"""Structured trace helpers for ecommerce AgentOps."""

from __future__ import annotations

import re
import time
import uuid
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

_SLUG_RE = re.compile(r"\W+", flags=re.UNICODE)
logger = logging.getLogger(__name__)


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
    """Build a stable run id. Timestamp is UTC (see Global Constraints)."""
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
    # [FIX-2] remember how many governance events existed when this node
    # started, so finish_trace_node can reference only the events emitted
    # *during* this node. Underscore-prefixed scratch key; popped on finish.
    start_event_count = len(state.get("governance", {}).get("events", []))
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
        "_start_event_count": start_event_count,
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
    # [FIX-2] reference only governance events emitted during this node.
    start_event_count = int(record.pop("_start_event_count", 0))
    end_event_count = len(state.get("governance", {}).get("events", []))
    record["governance_event_refs"] = list(range(start_event_count, end_event_count))
    return record


async def emit_trace(
    progress_callback: Callable[[str, dict], Awaitable[None]] | None,
    record: Mapping[str, Any],
) -> None:
    if progress_callback is None:
        return
    try:
        await progress_callback("trace_node_done", dict(record))
    except Exception:
        logger.warning(
            "[trace] progress_callback failed node=%s",
            record.get("node", ""),
            exc_info=True,
        )


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
