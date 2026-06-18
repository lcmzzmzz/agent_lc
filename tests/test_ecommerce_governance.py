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


import pytest

from multi_agents.ecommerce.runtime.policy_guard import (
    PolicyViolation,
    assert_tool_allowed,
    is_safe_url,
    redact_secrets,
    sanitize_source_url,
    validate_research_request,
)


def test_validate_research_request_rejects_invalid_depth():
    with pytest.raises(PolicyViolation) as exc:
        validate_research_request(
            query="portable blender",
            target_market="US",
            platforms=["amazon"],
            depth="extreme",
        )

    assert "depth" in str(exc.value)


def test_validate_research_request_rejects_invalid_market():
    with pytest.raises(PolicyViolation) as exc:
        validate_research_request(
            query="portable blender",
            target_market="CN",
            platforms=["amazon"],
            depth="standard",
        )

    assert "target_market" in str(exc.value)


def test_policy_blocks_unsafe_urls():
    assert is_safe_url("https://example.com/review") is True
    assert is_safe_url("file:///C:/secret.txt") is False
    assert is_safe_url("http://localhost:8000/admin") is False
    assert is_safe_url("http://127.0.0.1:8000/admin") is False
    assert is_safe_url("http://192.168.1.12/internal") is False


def test_sanitize_source_url_drops_unsafe_url():
    assert sanitize_source_url("file:///C:/secret.txt") == ""
    assert sanitize_source_url("https://example.com/review") == "https://example.com/review"


def test_redact_secrets_masks_sensitive_keys():
    payload = {
        "APIFY_API_TOKEN": "apify_api_secret",
        "authorization": "Bearer secret",
        "nested": {"password": "pw", "safe": "ok"},
    }

    redacted = redact_secrets(payload)

    assert redacted["APIFY_API_TOKEN"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "ok"


def test_tool_permission_boundaries():
    assert_tool_allowed("TrendResearchAgent", "search")
    with pytest.raises(PolicyViolation):
        assert_tool_allowed("ReportWriterAgent", "search")


from multi_agents.ecommerce.runtime.budget_manager import (
    BudgetConfig,
    BudgetManager,
)


def test_budget_manager_tracks_usage_and_limits():
    governance = empty_governance_state()
    budget = BudgetManager(governance, BudgetConfig(max_llm_calls=1, max_search_calls=2))

    assert budget.can_use("llm") is True
    budget.record("llm")
    assert governance["usage"]["llm_call_count"] == 1
    assert budget.can_use("llm") is False

    budget.record_degradation("OpportunityScoringAgent", "llm budget exceeded")
    summary = summarize_governance(governance)

    assert summary["budget_exceeded"] is True
    assert summary["degraded_by_budget"] is True


import asyncio

from multi_agents.ecommerce.runtime.execution_guard import ExecutionGuard


@pytest.mark.asyncio
async def test_execution_guard_retries_then_succeeds():
    governance = empty_governance_state()
    guard = ExecutionGuard(governance)
    attempts = 0

    async def flaky():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        return "ok"

    result = await guard.run(
        name="FlakyAgent",
        operation=flaky,
        timeout_ms=1000,
        max_retries=1,
    )

    assert result == "ok"
    summary = summarize_governance(governance)
    assert summary["retry_count"] == 1
    assert summary["failure_count"] == 0


@pytest.mark.asyncio
async def test_execution_guard_uses_fallback_after_failure():
    governance = empty_governance_state()
    guard = ExecutionGuard(governance)

    async def failing():
        raise RuntimeError("provider down")

    async def fallback():
        return "fallback"

    result = await guard.run(
        name="ReviewInsightAgent",
        operation=failing,
        timeout_ms=1000,
        max_retries=0,
        fallback=fallback,
        fallback_reason="provider down",
    )

    assert result == "fallback"
    summary = summarize_governance(governance)
    assert summary["fallback_count"] == 1
    assert summary["failure_count"] == 0


@pytest.mark.asyncio
async def test_budgeted_search_records_usage():
    from multi_agents.ecommerce.runtime.budget_manager import BudgetConfig, BudgetManager
    from multi_agents.ecommerce.tools.product_search import make_budgeted_search_fn

    governance = empty_governance_state()
    budget = BudgetManager(governance, BudgetConfig(max_search_calls=2))

    async def fake_search(query, max_results):
        return [{"title": "R", "href": "https://example.com/r", "body": "Body"}]

    wrapped = make_budgeted_search_fn(fake_search, budget)
    result = await wrapped("portable blender reviews", 1)

    assert result
    assert governance["usage"]["search_call_count"] == 1


@pytest.mark.asyncio
async def test_budgeted_search_returns_empty_when_budget_exceeded():
    from multi_agents.ecommerce.runtime.budget_manager import BudgetConfig, BudgetManager
    from multi_agents.ecommerce.tools.product_search import make_budgeted_search_fn

    governance = empty_governance_state()
    budget = BudgetManager(governance, BudgetConfig(max_search_calls=0))
    called = False

    async def fake_search(query, max_results):
        nonlocal called
        called = True
        return []

    wrapped = make_budgeted_search_fn(fake_search, budget)
    result = await wrapped("portable blender reviews", 1)

    assert result == []
    assert called is False
    assert governance["degraded_by_budget"] is True
