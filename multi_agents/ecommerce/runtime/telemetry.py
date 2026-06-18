from __future__ import annotations

import time
from typing import Any, TypedDict


class GovernanceEvent(TypedDict, total=False):
    kind: str
    agent: str
    detail: str
    timestamp_ms: int
    retry_count: int
    fallback_used: bool
    degraded_by_budget: bool
    policy_blocked: bool
    error_type: str
    error_message: str


def empty_governance_state() -> dict[str, Any]:
    return {
        "events": [],
        "usage": {
            "llm_call_count": 0,
            "search_call_count": 0,
            "scrape_call_count": 0,
            "external_api_call_count": 0,
            "estimated_cost_usd": 0.0,
        },
        "budget_exceeded": False,
        "degraded_by_budget": False,
    }


def record_event(
    governance: dict[str, Any],
    *,
    kind: str,
    agent: str,
    detail: str,
    retry_count: int = 0,
    fallback_used: bool = False,
    degraded_by_budget: bool = False,
    policy_blocked: bool = False,
    error_type: str = "",
    error_message: str = "",
) -> GovernanceEvent:
    event: GovernanceEvent = {
        "kind": kind,
        "agent": agent,
        "detail": detail,
        "timestamp_ms": int(time.time() * 1000),
        "retry_count": retry_count,
        "fallback_used": fallback_used,
        "degraded_by_budget": degraded_by_budget,
        "policy_blocked": policy_blocked,
    }
    if error_type:
        event["error_type"] = error_type
    if error_message:
        event["error_message"] = error_message
    governance.setdefault("events", []).append(event)
    if degraded_by_budget:
        governance["budget_exceeded"] = True
        governance["degraded_by_budget"] = True
    return event


def increment_usage(
    governance: dict[str, Any],
    key: str,
    amount: int | float = 1,
) -> None:
    usage = governance.setdefault("usage", {})
    usage[key] = usage.get(key, 0) + amount


def summarize_governance(governance: dict[str, Any] | None) -> dict[str, Any]:
    governance = governance or empty_governance_state()
    events = governance.get("events", [])
    usage = governance.get("usage", {})
    return {
        "failure_count": sum(1 for e in events if e.get("kind") == "failure"),
        "retry_count": sum(int(e.get("retry_count", 0)) for e in events),
        "fallback_count": sum(1 for e in events if e.get("fallback_used")),
        "policy_block_count": sum(1 for e in events if e.get("policy_blocked")),
        "budget_exceeded": bool(governance.get("budget_exceeded", False)),
        "degraded_by_budget": bool(governance.get("degraded_by_budget", False)),
        "llm_call_count": int(usage.get("llm_call_count", 0)),
        "search_call_count": int(usage.get("search_call_count", 0)),
        "scrape_call_count": int(usage.get("scrape_call_count", 0)),
        "external_api_call_count": int(usage.get("external_api_call_count", 0)),
        "estimated_cost_usd": round(float(usage.get("estimated_cost_usd", 0.0)), 6),
    }
