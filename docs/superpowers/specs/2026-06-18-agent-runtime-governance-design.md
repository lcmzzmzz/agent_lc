# Agent Runtime Governance Design

## Goal

Add an Agent Runtime Governance layer to EcomResearcher so the multi-agent workflow is not only functional, but also controlled under real product constraints: failure recovery, cost limits, and safety boundaries.

This layer should make every run auditable. A reviewer should be able to answer:

- Which agent failed or degraded?
- Which fallback path was used?
- How much budget was consumed?
- Which policy checks ran?
- Was any unsafe input, URL, tool request, or output blocked?

## Scope

In scope:

- Failure control for agent/tool execution.
- Budget tracking and budget-based degradation.
- Policy checks for inputs, tool permissions, URL access, secrets, and rendered output.
- Structured telemetry that feeds audit logs, evaluation summaries, and the demo evaluation page.
- Tests that prove the governance layer changes runtime behavior, not only logs metadata.

Out of scope for this phase:

- A full YAML policy engine.
- User accounts, billing, or persistent per-user quotas.
- Sandboxed browser execution.
- Replacing the existing LLM provider abstraction.

## Architecture

Add four small modules under `multi_agents/ecommerce/runtime/`:

1. `execution_guard.py`
   Wraps agent/tool calls with timeout, retry, fallback, and partial-result behavior.

2. `budget_manager.py`
   Tracks LLM, search, scrape, and external API usage against per-run and per-agent budgets.

3. `policy_guard.py`
   Enforces input validation, agent tool permissions, URL restrictions, and secret-safe logging.

4. `telemetry.py`
   Normalizes governance events into audit/evaluation-friendly records.

The goal is not to rewrite every agent. The first implementation should integrate at the existing workflow edges:

- `run_ecommerce_research()`
- `run_ecommerce_graph()`
- `default_search_fn()`
- Review scraping and fallback paths
- LLM helper calls where practical

## Failure Control

### Code Behavior

`ExecutionGuard` should provide a wrapper similar to:

```python
result = await guard.run(
    name="ReviewInsightAgent",
    operation=callable,
    timeout_ms=30000,
    max_retries=1,
    fallback=fallback_callable,
)
```

It records:

- `status`: `success`, `partial`, `failed`, or `degraded`
- `duration_ms`
- `retry_count`
- `fallback_used`
- `fallback_reason`
- `error_type`
- `error_message`

Recoverable failures should return partial data instead of crashing the whole graph. Examples:

- Apify review scraping returns zero rows -> Tavily fallback.
- LLM scoring fails -> rule-based scoring.
- Search provider fails -> empty evidence plus lower confidence.

Non-recoverable failures should be explicit and visible in `state["errors"]`.

### Resume/Portfolio Story

> Designed fault-tolerant multi-agent execution with per-agent timeout, retry, fallback, and partial-result degradation, ensuring research workflows continue even when external search or scraping providers fail.

Interview explanation:

> Each agent is treated as a recoverable runtime step. If Apify fails, ReviewInsightAgent degrades to Tavily and marks the report as lower-confidence instead of crashing. The audit log records the fallback path so users can see whether the report used true reviews or web summaries.

## Cost Control

### Code Behavior

`BudgetManager` should track usage for each run:

- `llm_call_count`
- `search_call_count`
- `scrape_call_count`
- `external_api_call_count`
- `estimated_cost_usd`
- `budget_exceeded`
- `degraded_by_budget`

Initial budget configuration can live in `config.py` or environment variables:

- `ECOMMERCE_MAX_LLM_CALLS`
- `ECOMMERCE_MAX_SEARCH_CALLS`
- `ECOMMERCE_MAX_SCRAPE_CALLS`
- `ECOMMERCE_MAX_ESTIMATED_COST_USD`

When budget is near or over limit:

- Stop extra search expansion.
- Prefer rule scoring over LLM scoring.
- Skip optional LLM summarization.
- Reduce `deep` behavior to `standard` behavior for optional branches.

The system should make budget degradation explicit in both `audit_log` and `evaluation_summary`.

### Resume/Portfolio Story

> Built a budget-aware agent runtime that tracks LLM/search/scraping calls, enforces per-run and per-agent limits, and gracefully degrades from LLM-based reasoning to deterministic rules when budgets are exceeded.

Interview explanation:

> I did not let agents call APIs indefinitely. Each run has a budget envelope. When the budget is exhausted, the workflow keeps producing a report, but optional LLM steps are skipped and deterministic fallbacks are used.

## Safety Boundaries

### Code Behavior

`PolicyGuard` should enforce:

- Input validation:
  - Query length limit.
  - `depth` must be `fast`, `standard`, or `deep`.
  - `target_market` must be from an allowlist such as `US`, `UK`, `DE`, `JP`.
  - `platforms` must be from supported platform names.

- Tool permissions:
  - Trend and competitor agents can call search.
  - Review agent can call review scraping and fallback search.
  - Report writer can only read state and produce markdown.
  - Quality reviewer can only read state and produce quality results.

- URL restrictions:
  - Allow only `http` and `https`.
  - Block local files, private IP ranges, and internal hostnames.
  - Normalize or drop unsafe source URLs before report rendering.

- Secret-safe logging:
  - Redact values for keys containing `token`, `api_key`, `authorization`, or `password`.
  - Never write `.env` contents or raw provider headers to logs.

- Output safety:
  - Keep frontend report rendering sanitized with DOMPurify.
  - Sanitize markdown links before writing reports where possible.

Policy decisions should be visible in telemetry:

- `policy_checked`
- `policy_blocked`
- `blocked_reason`
- `blocked_tool`
- `sanitized_output`

### Resume/Portfolio Story

> Implemented policy-based safety boundaries for multi-agent workflows, including tool-level permissions, input validation, secret-safe logging, URL restrictions, and sanitized report rendering.

Interview explanation:

> I treated agents as bounded execution units. A report-writing agent should not be able to make network calls, and external source URLs should not be allowed to point to local files or private addresses. The policy layer blocks those cases before they reach the workflow.

## Data Flow

1. API or CLI creates initial state.
2. `PolicyGuard` validates user input.
3. `BudgetManager` starts a run budget.
4. `run_ecommerce_graph()` executes each stage through `ExecutionGuard`.
5. Search, scraping, and LLM wrappers report usage to `BudgetManager`.
6. Fallbacks and policy blocks emit telemetry events.
7. `RunTelemetry` merges governance events into:
   - `audit_log`
   - `evaluation_summary`
   - `output_paths`
   - frontend evaluation metrics

## Evaluation Fields

Extend `evaluation_summary` with:

- `failure_count`
- `retry_count`
- `fallback_count`
- `policy_block_count`
- `budget_exceeded`
- `degraded_by_budget`
- `llm_call_count`
- `search_call_count`
- `scrape_call_count`
- `estimated_cost_usd`

These fields make the demo evaluation page more than a score dashboard. It becomes proof that the workflow is governed.

## Testing Strategy

Add focused tests for:

- Apify failure triggers fallback and records fallback telemetry.
- LLM scoring failure triggers rule fallback and records degraded status.
- Budget exhaustion skips optional LLM summarization.
- Invalid `depth`, market, or platform is rejected before graph execution.
- Unsafe URLs such as `file://`, `localhost`, and private IP ranges are blocked or dropped.
- Secret values are redacted from telemetry/log payloads.
- Evaluation summaries include governance metrics.

Tests should use injected fake search, fake LLM, and fake scraper functions. No test should require real Apify, Tavily, or OpenAI credentials.

## Implementation Order

1. Add telemetry schema and evaluation fields.
2. Add `PolicyGuard` input validation and secret redaction.
3. Add `BudgetManager` counters with non-invasive defaults.
4. Add `ExecutionGuard` around the highest-risk paths:
   - Review scraping
   - LLM scoring
   - default search
5. Surface governance metrics in `ecommerce-eval.html`.
6. Update README with a short Agent Runtime Governance section.

## Success Criteria

- A failed external provider does not crash the whole ecommerce workflow.
- A run can show exactly when fallback, retry, or budget degradation happened.
- Non-US markets remain preserved during fallback search.
- Invalid inputs are rejected before expensive work starts.
- Secrets do not appear in audit logs, evaluation JSON, or runtime logs.
- Governance behavior is covered by automated tests.

