# Agent Runtime Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a governance layer for EcomResearcher that controls failures, cost, and safety boundaries while exposing auditable runtime metrics.

**Architecture:** Add focused runtime modules under `multi_agents/ecommerce/runtime/` and integrate them at workflow edges instead of rewriting all agents. Governance events flow into `state["governance"]`, then into `audit_log`, `evaluation_summary`, the demo evaluation page, and README portfolio language.

**Tech Stack:** Python 3.12, FastAPI-facing ecommerce runner, pytest with injected fake search/LLM/scraper functions, static HTML/CSS/JS for `frontend/ecommerce-eval.html`.

---

## File Structure

- Create: `multi_agents/ecommerce/runtime/__init__.py`
  Exports the runtime helpers used by runner, graph, tools, and tests.

- Create: `multi_agents/ecommerce/runtime/telemetry.py`
  Defines `GovernanceEvent`, `empty_governance_state()`, `record_event()`, and `summarize_governance()`.

- Create: `multi_agents/ecommerce/runtime/policy_guard.py`
  Validates inputs, checks tool permissions, blocks unsafe URLs, and redacts secret-like values.

- Create: `multi_agents/ecommerce/runtime/budget_manager.py`
  Tracks run-level and per-operation budgets for LLM/search/scrape/external API calls.

- Create: `multi_agents/ecommerce/runtime/execution_guard.py`
  Wraps async operations with timeout, retry, fallback, and telemetry recording.

- Modify: `multi_agents/ecommerce/state.py`
  Add optional `governance` field and initialize it in `create_initial_state()`.

- Modify: `multi_agents/ecommerce/evaluation.py`
  Merge governance summary fields into `build_evaluation_summary()`.

- Modify: `multi_agents/ecommerce/runner.py`
  Validate inputs before graph execution and initialize governance/budget state.

- Modify: `multi_agents/ecommerce/graph.py`
  Use the execution guard around high-level research stages where appropriate.

- Modify: `multi_agents/ecommerce/agents/opportunity_scorer.py`
  Respect LLM budget exhaustion and record LLM-to-rule degradation.

- Modify: `multi_agents/ecommerce/tools/product_search.py`
  Record search call usage through optional budget-aware wrappers.

- Modify: `multi_agents/ecommerce/tools/review_scraper.py`
  Record external API/scrape attempts and fallback telemetry for review scraping.

- Modify: `frontend/ecommerce-eval.html`
  Surface governance metrics in KPI cards and the details table.

- Modify: `README.md`
  Add a short portfolio section for Agent Runtime Governance.

- Test: `tests/test_ecommerce_governance.py`
  New focused tests for telemetry, policy, budget, and execution guard primitives.

- Modify: `tests/test_ecommerce_runner.py`
  Add tests for invalid input rejection and evaluation summary governance fields.

- Modify: `tests/test_ecommerce_agents.py`
  Add test for budget exhaustion causing rule scoring instead of LLM scoring.

- Modify: `tests/test_ecommerce_review_scraper.py`
  Add/adjust tests to assert fallback telemetry is recorded when Apify returns no reviews.

---

### Task 1: Runtime Telemetry Foundation

**Files:**
- Create: `multi_agents/ecommerce/runtime/__init__.py`
- Create: `multi_agents/ecommerce/runtime/telemetry.py`
- Modify: `multi_agents/ecommerce/state.py`
- Modify: `multi_agents/ecommerce/evaluation.py`
- Test: `tests/test_ecommerce_governance.py`

- [ ] **Step 1: Write failing telemetry tests**

Add this new file:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py::test_record_event_updates_governance_summary tests/test_ecommerce_governance.py::test_create_initial_state_contains_governance_state tests/test_ecommerce_governance.py::test_evaluation_summary_includes_governance_metrics -q
```

Expected: FAIL because `multi_agents.ecommerce.runtime.telemetry` does not exist and `state["governance"]` is not initialized.

- [ ] **Step 3: Implement telemetry module**

Create `multi_agents/ecommerce/runtime/__init__.py`:

```python
"""Runtime governance helpers for EcomResearcher."""
```

Create `multi_agents/ecommerce/runtime/telemetry.py`:

```python
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
```

- [ ] **Step 4: Add governance to state**

Modify `multi_agents/ecommerce/state.py`:

```python
from multi_agents.ecommerce.runtime.telemetry import empty_governance_state
```

Add this field to `EcommerceResearchState`:

```python
    governance: dict[str, Any]
```

Add this key in `create_initial_state()`:

```python
        "governance": empty_governance_state(),
```

- [ ] **Step 5: Merge governance into evaluation summary**

Modify `multi_agents/ecommerce/evaluation.py`:

```python
from multi_agents.ecommerce.runtime.telemetry import summarize_governance
```

Inside `build_evaluation_summary()`, before the return:

```python
    governance_summary = summarize_governance(state.get("governance"))
```

Change the return to build a base dict and merge governance:

```python
    summary = {
        "overall_score": score.get("overall_score", 0.0),
        "confidence": confidence,
        "evidence_count": evidence_count,
        "fallback_count": max(fallback_count, governance_summary["fallback_count"]),
        "duration_ms": duration_ms,
        "recommendation": score.get("recommendation", ""),
        "scored_by": score.get("scored_by", "rule"),
        "quality_passed": state.get("quality_check", {}).get("passed", False),
        "review_source": review.get("review_source", "unknown"),
        "review_count": review.get("review_count", 0),
    }
    summary.update(governance_summary)
    return summary
```

- [ ] **Step 6: Run task tests**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_state.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit telemetry foundation**

Run:

```powershell
git add -- multi_agents/ecommerce/runtime/__init__.py multi_agents/ecommerce/runtime/telemetry.py multi_agents/ecommerce/state.py multi_agents/ecommerce/evaluation.py tests/test_ecommerce_governance.py
git commit -m "feat(ecommerce): add governance telemetry foundation"
```

---

### Task 2: Policy Guard

**Files:**
- Create: `multi_agents/ecommerce/runtime/policy_guard.py`
- Modify: `multi_agents/ecommerce/runner.py`
- Modify: `multi_agents/ecommerce/tools/source_normalizer.py`
- Test: `tests/test_ecommerce_governance.py`
- Test: `tests/test_ecommerce_runner.py`

- [ ] **Step 1: Add failing policy tests**

Append to `tests/test_ecommerce_governance.py`:

```python
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
```

Append to `tests/test_ecommerce_runner.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py tests/test_ecommerce_runner.py::test_runner_rejects_invalid_depth_before_search -q
```

Expected: FAIL because `policy_guard.py` does not exist and runner has not integrated validation.

- [ ] **Step 3: Implement policy guard**

Create `multi_agents/ecommerce/runtime/policy_guard.py`:

```python
from __future__ import annotations

import copy
import ipaddress
from typing import Any
from urllib.parse import urlparse


ALLOWED_DEPTHS = {"fast", "standard", "deep"}
ALLOWED_MARKETS = {"US", "UK", "DE", "JP"}
ALLOWED_PLATFORMS = {"amazon", "google", "reddit", "tiktok", "youtube", "web"}
SECRET_KEY_PARTS = ("token", "api_key", "apikey", "authorization", "password", "secret")

TOOL_PERMISSIONS = {
    "TrendResearchAgent": {"search"},
    "CompetitorAnalyzerAgent": {"search"},
    "ReviewInsightAgent": {"review_scrape", "search"},
    "OpportunityScoringAgent": {"llm", "rule_score"},
    "ReportWriterAgent": {"state_read", "markdown_write"},
    "QualityReviewerAgent": {"state_read", "quality_check"},
}


class PolicyViolation(ValueError):
    pass


def validate_research_request(
    *,
    query: str,
    target_market: str,
    platforms: list[str] | None,
    depth: str,
) -> None:
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        raise PolicyViolation("query must not be empty")
    if len(cleaned_query) > 200:
        raise PolicyViolation("query must be 200 characters or fewer")
    if depth not in ALLOWED_DEPTHS:
        raise PolicyViolation(f"depth must be one of {sorted(ALLOWED_DEPTHS)}")
    if target_market not in ALLOWED_MARKETS:
        raise PolicyViolation(f"target_market must be one of {sorted(ALLOWED_MARKETS)}")
    invalid_platforms = [p for p in (platforms or []) if p not in ALLOWED_PLATFORMS]
    if invalid_platforms:
        raise PolicyViolation(f"unsupported platforms: {invalid_platforms}")


def assert_tool_allowed(agent: str, tool: str) -> None:
    allowed = TOOL_PERMISSIONS.get(agent, set())
    if tool not in allowed:
        raise PolicyViolation(f"{agent} is not allowed to use tool '{tool}'")


def is_safe_url(url: str) -> bool:
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if not host:
        return False
    if host in {"localhost"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local)


def sanitize_source_url(url: str) -> str:
    return url if is_safe_url(url) else ""


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_l = str(key).lower()
            if any(part in key_l for part in SECRET_KEY_PARTS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return copy.deepcopy(value)
```

- [ ] **Step 4: Integrate request validation in runner**

Modify `multi_agents/ecommerce/runner.py` imports:

```python
from multi_agents.ecommerce.runtime.policy_guard import (
    PolicyViolation,
    validate_research_request,
)
```

At the start of `run_ecommerce_research()` after log setup:

```python
        try:
            validate_research_request(
                query=query,
                target_market=target_market,
                platforms=platforms or ["amazon", "google"],
                depth=depth,
            )
        except PolicyViolation as exc:
            raise ValueError(str(exc)) from exc
```

Place this before `create_initial_state(...)` so invalid requests fail before search/LLM work starts.

- [ ] **Step 5: Sanitize normalized source URLs**

Modify `multi_agents/ecommerce/tools/source_normalizer.py`:

```python
from multi_agents.ecommerce.runtime.policy_guard import sanitize_source_url
```

Where the normalized URL is assigned, wrap it:

```python
    url = sanitize_source_url(raw.get("href") or raw.get("url") or raw.get("link") or "")
```

If the file uses a different local variable name, keep the existing structure but ensure unsafe URLs become `""`.

- [ ] **Step 6: Run policy tests**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py tests/test_ecommerce_runner.py tests/test_ecommerce_tools.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit policy guard**

Run:

```powershell
git add -- multi_agents/ecommerce/runtime/policy_guard.py multi_agents/ecommerce/runner.py multi_agents/ecommerce/tools/source_normalizer.py tests/test_ecommerce_governance.py tests/test_ecommerce_runner.py
git commit -m "feat(ecommerce): add policy guard for runtime safety"
```

---

### Task 3: Budget Manager

**Files:**
- Create: `multi_agents/ecommerce/runtime/budget_manager.py`
- Modify: `multi_agents/ecommerce/config.py`
- Modify: `multi_agents/ecommerce/agents/opportunity_scorer.py`
- Test: `tests/test_ecommerce_governance.py`
- Test: `tests/test_ecommerce_agents.py`

- [ ] **Step 1: Add failing budget tests**

Append to `tests/test_ecommerce_governance.py`:

```python
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
```

Append to `tests/test_ecommerce_agents.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py::test_budget_manager_tracks_usage_and_limits tests/test_ecommerce_agents.py::test_opportunity_scoring_skips_llm_when_budget_exhausted -q
```

Expected: FAIL because `budget_manager.py` does not exist and `run_opportunity_scoring()` has no `budget_manager` parameter.

- [ ] **Step 3: Implement budget manager**

Create `multi_agents/ecommerce/runtime/budget_manager.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multi_agents.ecommerce.runtime.telemetry import increment_usage, record_event


USAGE_KEYS = {
    "llm": "llm_call_count",
    "search": "search_call_count",
    "scrape": "scrape_call_count",
    "external_api": "external_api_call_count",
}


@dataclass(frozen=True)
class BudgetConfig:
    max_llm_calls: int = 20
    max_search_calls: int = 80
    max_scrape_calls: int = 20
    max_external_api_calls: int = 20
    max_estimated_cost_usd: float = 1.0


class BudgetManager:
    def __init__(self, governance: dict[str, Any], config: BudgetConfig | None = None):
        self.governance = governance
        self.config = config or BudgetConfig()

    def _usage_key(self, kind: str) -> str:
        if kind not in USAGE_KEYS:
            raise ValueError(f"unknown budget kind: {kind}")
        return USAGE_KEYS[kind]

    def _limit_for(self, kind: str) -> int:
        return {
            "llm": self.config.max_llm_calls,
            "search": self.config.max_search_calls,
            "scrape": self.config.max_scrape_calls,
            "external_api": self.config.max_external_api_calls,
        }[kind]

    def can_use(self, kind: str) -> bool:
        usage = self.governance.setdefault("usage", {})
        return int(usage.get(self._usage_key(kind), 0)) < self._limit_for(kind)

    def record(self, kind: str, estimated_cost_usd: float = 0.0) -> None:
        increment_usage(self.governance, self._usage_key(kind), 1)
        if estimated_cost_usd:
            increment_usage(self.governance, "estimated_cost_usd", estimated_cost_usd)
        usage = self.governance.setdefault("usage", {})
        if float(usage.get("estimated_cost_usd", 0.0)) > self.config.max_estimated_cost_usd:
            self.governance["budget_exceeded"] = True

    def record_degradation(self, agent: str, detail: str) -> None:
        self.governance["budget_exceeded"] = True
        self.governance["degraded_by_budget"] = True
        record_event(
            self.governance,
            kind="budget",
            agent=agent,
            detail=detail,
            degraded_by_budget=True,
        )
```

- [ ] **Step 4: Add config loader**

Modify `multi_agents/ecommerce/config.py`:

```python
import os
from multi_agents.ecommerce.runtime.budget_manager import BudgetConfig
```

Add:

```python
def get_budget_config() -> BudgetConfig:
    return BudgetConfig(
        max_llm_calls=int(os.environ.get("ECOMMERCE_MAX_LLM_CALLS", "20")),
        max_search_calls=int(os.environ.get("ECOMMERCE_MAX_SEARCH_CALLS", "80")),
        max_scrape_calls=int(os.environ.get("ECOMMERCE_MAX_SCRAPE_CALLS", "20")),
        max_external_api_calls=int(os.environ.get("ECOMMERCE_MAX_EXTERNAL_API_CALLS", "20")),
        max_estimated_cost_usd=float(os.environ.get("ECOMMERCE_MAX_ESTIMATED_COST_USD", "1.0")),
    )
```

- [ ] **Step 5: Integrate LLM budget in scoring**

Modify `multi_agents/ecommerce/agents/opportunity_scorer.py` imports:

```python
from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
```

Change signature:

```python
async def run_opportunity_scoring(
    state: EcommerceResearchState,
    *,
    llm_fn: LlmFn | None = None,
    budget_manager: BudgetManager | None = None,
) -> EcommerceResearchState:
```

Replace:

```python
    if llm_fn is not None:
```

with:

```python
    if llm_fn is not None and budget_manager is not None and not budget_manager.can_use("llm"):
        budget_manager.record_degradation("OpportunityScoringAgent", "llm budget exceeded")
        llm_fn = None

    if llm_fn is not None:
        if budget_manager is not None:
            budget_manager.record("llm")
```

- [ ] **Step 6: Run budget tests**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py tests/test_ecommerce_agents.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit budget manager**

Run:

```powershell
git add -- multi_agents/ecommerce/runtime/budget_manager.py multi_agents/ecommerce/config.py multi_agents/ecommerce/agents/opportunity_scorer.py tests/test_ecommerce_governance.py tests/test_ecommerce_agents.py
git commit -m "feat(ecommerce): add budget manager for llm governance"
```

---

### Task 4: Execution Guard

**Files:**
- Create: `multi_agents/ecommerce/runtime/execution_guard.py`
- Modify: `multi_agents/ecommerce/graph.py`
- Modify: `multi_agents/ecommerce/runner.py`
- Modify: `multi_agents/ecommerce/agents/review_insight.py`
- Test: `tests/test_ecommerce_governance.py`
- Test: `tests/test_ecommerce_review_scraper.py`

- [ ] **Step 1: Add failing execution guard tests**

Append to `tests/test_ecommerce_governance.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py::test_execution_guard_retries_then_succeeds tests/test_ecommerce_governance.py::test_execution_guard_uses_fallback_after_failure -q
```

Expected: FAIL because `execution_guard.py` does not exist.

- [ ] **Step 3: Implement execution guard**

Create `multi_agents/ecommerce/runtime/execution_guard.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from multi_agents.ecommerce.runtime.telemetry import record_event

T = TypeVar("T")


class ExecutionGuard:
    def __init__(self, governance: dict[str, Any]):
        self.governance = governance

    async def run(
        self,
        *,
        name: str,
        operation: Callable[[], Awaitable[T]],
        timeout_ms: int,
        max_retries: int = 0,
        fallback: Callable[[], Awaitable[T]] | None = None,
        fallback_reason: str = "",
    ) -> T:
        retry_count = 0
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(operation(), timeout=timeout_ms / 1000)
                if retry_count:
                    record_event(
                        self.governance,
                        kind="retry",
                        agent=name,
                        detail="operation succeeded after retry",
                        retry_count=retry_count,
                    )
                return result
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    retry_count += 1
                    continue

        if fallback is not None:
            result = await fallback()
            record_event(
                self.governance,
                kind="fallback",
                agent=name,
                detail=fallback_reason or str(last_exc),
                retry_count=retry_count,
                fallback_used=True,
                error_type=type(last_exc).__name__ if last_exc else "",
                error_message=str(last_exc) if last_exc else "",
            )
            return result

        record_event(
            self.governance,
            kind="failure",
            agent=name,
            detail=str(last_exc),
            retry_count=retry_count,
            error_type=type(last_exc).__name__ if last_exc else "",
            error_message=str(last_exc) if last_exc else "",
        )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"{name} failed without exception")
```

- [ ] **Step 4: Pass budget manager through graph**

Modify `multi_agents/ecommerce/graph.py` imports:

```python
from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
from multi_agents.ecommerce.runtime.execution_guard import ExecutionGuard
```

Change `run_ecommerce_graph()` signature:

```python
    budget_manager: BudgetManager | None = None,
```

Change opportunity scoring call:

```python
    state = await run_opportunity_scoring(
        state,
        llm_fn=llm_fn,
        budget_manager=budget_manager,
    )
```

- [ ] **Step 5: Initialize budget manager in runner**

Modify `multi_agents/ecommerce/runner.py` imports:

```python
from multi_agents.ecommerce.config import get_budget_config
from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
```

After `state = create_initial_state(...)`, add:

```python
        budget_manager = BudgetManager(state["governance"], get_budget_config())
```

Pass it into `run_ecommerce_graph()`:

```python
            budget_manager=budget_manager,
```

- [ ] **Step 6: Record review fallback telemetry**

Modify `multi_agents/ecommerce/agents/review_insight.py`:

```python
from multi_agents.ecommerce.runtime.telemetry import record_event
```

After setting `fallback_reason = "apify returned 0 reviews"`:

```python
            if "governance" in state:
                record_event(
                    state["governance"],
                    kind="fallback",
                    agent="ReviewInsightAgent",
                    detail=fallback_reason,
                    fallback_used=True,
                )
```

After `fallback_reason = f"apify failed: {exc}"`:

```python
            if "governance" in state:
                record_event(
                    state["governance"],
                    kind="fallback",
                    agent="ReviewInsightAgent",
                    detail=fallback_reason,
                    fallback_used=True,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
```

- [ ] **Step 7: Run execution guard tests**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py tests/test_ecommerce_review_scraper.py tests/test_ecommerce_runner.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit execution guard integration**

Run:

```powershell
git add -- multi_agents/ecommerce/runtime/execution_guard.py multi_agents/ecommerce/graph.py multi_agents/ecommerce/runner.py multi_agents/ecommerce/agents/review_insight.py tests/test_ecommerce_governance.py tests/test_ecommerce_review_scraper.py
git commit -m "feat(ecommerce): add execution guard and fallback telemetry"
```

---

### Task 5: Govern Search and External API Usage

**Files:**
- Modify: `multi_agents/ecommerce/tools/product_search.py`
- Modify: `multi_agents/ecommerce/tools/review_scraper.py`
- Modify: `multi_agents/ecommerce/runner.py`
- Test: `tests/test_ecommerce_governance.py`
- Test: `tests/test_ecommerce_runner.py`
- Test: `tests/test_ecommerce_review_scraper.py`

- [ ] **Step 1: Add failing usage tracking tests**

Append to `tests/test_ecommerce_governance.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py::test_budgeted_search_records_usage tests/test_ecommerce_governance.py::test_budgeted_search_returns_empty_when_budget_exceeded -q
```

Expected: FAIL because `make_budgeted_search_fn()` does not exist.

- [ ] **Step 3: Implement budgeted search wrapper**

Modify `multi_agents/ecommerce/tools/product_search.py` imports:

```python
from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
```

Add:

```python
def make_budgeted_search_fn(search_fn: SearchFn, budget_manager: BudgetManager | None) -> SearchFn:
    async def wrapped(query: str, max_results: int) -> list[dict[str, Any]]:
        if budget_manager is not None:
            if not budget_manager.can_use("search"):
                budget_manager.record_degradation("SearchFn", "search budget exceeded")
                return []
            budget_manager.record("search")
        return await search_fn(query, max_results)

    return wrapped
```

- [ ] **Step 4: Wrap search function in runner**

Modify `multi_agents/ecommerce/runner.py` imports:

```python
from multi_agents.ecommerce.tools.product_search import SearchFn, make_budgeted_search_fn
```

Before calling `run_ecommerce_graph()`:

```python
        resolved_search_fn = make_budgeted_search_fn(
            _resolve_search_fn(search_fn),
            budget_manager,
        )
```

Pass:

```python
            search_fn=resolved_search_fn,
```

- [ ] **Step 5: Record Apify external API attempts**

Modify `multi_agents/ecommerce/tools/review_scraper.py`:

Change `ApifyReviewScraper.__init__` signature:

```python
    def __init__(
        self,
        token: str,
        actors: dict[str, str] | None = None,
        country: str = "US",
        governance: dict[str, Any] | None = None,
    ):
```

Inside `__init__`:

```python
        self.governance = governance
```

Before each `requests.post(...)` in `_search_asins()` and `_fetch_reviews()`, add:

```python
                if self.governance is not None:
                    from multi_agents.ecommerce.runtime.telemetry import increment_usage

                    increment_usage(self.governance, "external_api_call_count", 1)
```

Change `get_review_scraper()` signature:

```python
def get_review_scraper(
    search_fn: SearchFn | None = None,
    governance: dict[str, Any] | None = None,
) -> tuple[ReviewSource, str | None]:
```

Pass governance into `ApifyReviewScraper(...)`.

Modify `run_review_insight()` call:

```python
    scraper, fallback_reason = get_review_scraper(search_fn, governance=state.get("governance"))
```

- [ ] **Step 6: Run usage tests**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_governance.py tests/test_ecommerce_runner.py tests/test_ecommerce_review_scraper.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit usage governance**

Run:

```powershell
git add -- multi_agents/ecommerce/tools/product_search.py multi_agents/ecommerce/tools/review_scraper.py multi_agents/ecommerce/runner.py multi_agents/ecommerce/agents/review_insight.py tests/test_ecommerce_governance.py tests/test_ecommerce_runner.py tests/test_ecommerce_review_scraper.py
git commit -m "feat(ecommerce): track governed search and api usage"
```

---

### Task 6: Frontend Evaluation Metrics

**Files:**
- Modify: `frontend/ecommerce-eval.html`
- Modify: `scripts/export_ecommerce_demo_cases.py`
- Test: `tests/test_ecommerce_demo_export.py`

- [ ] **Step 1: Add failing demo export test for governance fields**

Extend `tests/test_ecommerce_demo_export.py` so the fake successful case summary includes governance fields. Add assertions like:

```python
def test_manifest_preserves_governance_summary_fields(tmp_path, monkeypatch):
    from scripts import export_ecommerce_demo_cases as exporter

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
        "confidence": 0.7,
        "evidence_count": 3,
        "fallback_count": 1,
        "duration_ms": 1000,
        "quality_passed": True,
        "failure_count": 0,
        "retry_count": 1,
        "policy_block_count": 0,
        "budget_exceeded": False,
        "degraded_by_budget": False,
        "llm_call_count": 2,
        "search_call_count": 6,
        "scrape_call_count": 0,
        "estimated_cost_usd": 0.02,
    }

    entry = exporter._build_success_entry(case, summary)

    assert entry["summary"]["retry_count"] == 1
    assert entry["summary"]["llm_call_count"] == 2
    assert entry["summary"]["estimated_cost_usd"] == 0.02
```

If `_build_success_entry()` has a different signature, keep the assertion intent and use the existing helper shape.

- [ ] **Step 2: Run test to verify it fails if fields are dropped**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_demo_export.py -q
```

Expected: FAIL only if exporter filters summary fields. If it already preserves all summary fields, this step may PASS; keep the test as regression coverage.

- [ ] **Step 3: Update evaluation page KPIs**

Modify `frontend/ecommerce-eval.html`:

Add governance totals near KPI calculation:

```javascript
  const totalRetries = metricRows.reduce((a,r)=>a+(r.s.retry_count||0),0);
  const totalPolicyBlocks = metricRows.reduce((a,r)=>a+(r.s.policy_block_count||0),0);
  const totalLlmCalls = metricRows.reduce((a,r)=>a+(r.s.llm_call_count||0),0);
  const totalSearchCalls = metricRows.reduce((a,r)=>a+(r.s.search_call_count||0),0);
```

Update KPI HTML to include a fifth/sixth card or replace the existing evidence card:

```javascript
    <div class="kpi"><div class="k">重试 / 策略拦截</div><div class="v">${totalRetries} <span style="color:var(--mut); font-size:14px;">/ ${totalPolicyBlocks}</span></div></div>
    <div class="kpi"><div class="k">LLM / Search 调用</div><div class="v">${totalLlmCalls} <span style="color:var(--mut); font-size:14px;">/ ${totalSearchCalls}</span></div></div>
```

Add table headers after `Fallbacks`:

```html
            <th class="num">Retries</th>
            <th class="num">Policy Blocks</th>
            <th class="num">LLM/Search</th>
```

Add row cells for success:

```javascript
        <td class="num">${s.retry_count==null?"-":s.retry_count}</td>
        <td class="num ${s.policy_block_count>0?'bad':''}">${s.policy_block_count==null?"-":s.policy_block_count}</td>
        <td class="num">${s.llm_call_count||0}/${s.search_call_count||0}</td>
```

Add matching `-` cells in the error row.

- [ ] **Step 4: Run HTML smoke check**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_demo_export.py -q
```

Expected: PASS. There may be no automated HTML test yet; manually inspect the diff to ensure the table column count matches headers.

- [ ] **Step 5: Commit frontend governance metrics**

Run:

```powershell
git add -- frontend/ecommerce-eval.html scripts/export_ecommerce_demo_cases.py tests/test_ecommerce_demo_export.py
git commit -m "feat(ecommerce): surface governance metrics in evaluation page"
```

---

### Task 7: README Portfolio Update

**Files:**
- Modify: `README.md`
- Modify: `docs/ecommerce-architecture-guide.md`

- [ ] **Step 1: Add README governance section**

Modify `README.md` near the EcomResearcher portfolio section:

```markdown
### Agent Runtime Governance

EcomResearcher includes a lightweight governance layer around the multi-agent workflow:

- **Failure control:** per-step retry, fallback, and partial-result degradation so external provider failures do not crash the full report.
- **Cost control:** per-run budgets for LLM, search, scrape, and external API calls, with graceful degradation to deterministic rule scoring.
- **Safety boundaries:** input validation, tool-level permissions, unsafe URL filtering, secret-safe logging, and sanitized report rendering.
- **Auditability:** every run exports governance metrics such as fallback count, retry count, policy blocks, budget degradation, and provider usage.
```

- [ ] **Step 2: Add architecture guide note**

Modify `docs/ecommerce-architecture-guide.md` with:

```markdown
## Runtime Governance Layer

The governance layer sits around the agent graph rather than inside a single agent. `PolicyGuard` validates requests before execution, `BudgetManager` tracks expensive operations during execution, `ExecutionGuard` records retries/fallbacks around risky calls, and telemetry merges those events into audit logs and evaluation summaries.
```

- [ ] **Step 3: Verify docs diff**

Run:

```powershell
git diff -- README.md docs/ecommerce-architecture-guide.md
```

Expected: Diff shows only the governance documentation additions.

- [ ] **Step 4: Commit docs update**

Run:

```powershell
git add -- README.md docs/ecommerce-architecture-guide.md
git commit -m "docs(ecommerce): describe agent runtime governance"
```

---

### Task 8: Full Verification

**Files:**
- No new files unless test failures reveal necessary targeted fixes.

- [ ] **Step 1: Run full ecommerce test suite**

Run:

```powershell
& 'D:\conda\python.exe' -m pytest tests/test_ecommerce_state.py tests/test_ecommerce_tools.py tests/test_ecommerce_agents.py tests/test_ecommerce_review_scraper.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_runner.py tests/test_ecommerce_demo_export.py tests/test_ecommerce_governance.py -q
```

Expected: PASS. Existing pytest config may emit `Unknown config option: asyncio_fixture_loop_scope`; do not treat that warning as a failure.

- [ ] **Step 2: Run Python compile check**

Run:

```powershell
& 'D:\conda\python.exe' -m py_compile multi_agents/ecommerce/runtime/telemetry.py multi_agents/ecommerce/runtime/policy_guard.py multi_agents/ecommerce/runtime/budget_manager.py multi_agents/ecommerce/runtime/execution_guard.py multi_agents/ecommerce/runner.py multi_agents/ecommerce/graph.py multi_agents/ecommerce/agents/opportunity_scorer.py multi_agents/ecommerce/agents/review_insight.py multi_agents/ecommerce/tools/product_search.py multi_agents/ecommerce/tools/review_scraper.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run diff whitespace check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors. CRLF warnings in PowerShell output are acceptable if no diff-check error is reported.

- [ ] **Step 4: Review final status**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected: only intentional files are modified or the working tree is clean after commits.

- [ ] **Step 5: Final verification commit if needed**

If verification required a small fix, commit it:

```powershell
git add -- <changed-files>
git commit -m "fix(ecommerce): stabilize governance verification"
```

If no fix was needed, do not create an empty commit.

---

## Self-Review

- Spec coverage: failure control is covered by Tasks 1, 4, and 5; cost control by Tasks 1, 3, 5, and 6; safety boundaries by Task 2; evaluation and portfolio visibility by Tasks 1, 6, and 7; verification by Task 8.
- Completion scan: no unresolved gaps or shorthand implementation steps are intentionally left in this plan.
- Type consistency: `governance` is a dict on `EcommerceResearchState`; `BudgetManager`, `ExecutionGuard`, and policy helpers all accept or mutate that dict; evaluation reads through `summarize_governance()`.
