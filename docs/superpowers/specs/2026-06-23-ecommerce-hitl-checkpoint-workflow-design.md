# EcomResearcher HITL Checkpoint Workflow Design

Date: 2026-06-23

## Context

The current `multi_agents/ecommerce` project already has a working ecommerce research chain:

- `multi_agents/ecommerce/graph.py` uses LangGraph `StateGraph` for `planner -> {trend, competitor, review} -> scoring -> writer -> quality`.
- `multi_agents/ecommerce/runner.py` owns the end-to-end entry point, artifact writes, evaluation summary, optional MCP search augmentation, and optional visual concept generation.
- `multi_agents/ecommerce/runtime/run_store.py` can load completed run artifacts by `run_id` and save post-run human review.
- `backend/server/ecommerce_api.py` exposes synchronous research, WebSocket progress, run lookup, eval, and post-run human review APIs.
- `frontend/ecommerce.html` is the main static workflow UI. `frontend/ecommerce-review.html` and `frontend/ecommerce-eval.html` exist, but the new requirement is that all core research, interrupt, resume, review, and final inspection happen in one page.
- Existing "human review" is post-run annotation. It does not pause a live run, does not resume the same graph checkpoint, and does not let human feedback change downstream execution.

This design upgrades HITL from post-run labels to real mid-run checkpoints. The user should be able to review the generated research plan before any external search happens, then review evidence after trend/competitor/review finish and before scoring/report/visual generation.

LangGraph's official interrupt model is the right primitive: `interrupt(...)` pauses graph execution and surfaces a JSON-serializable payload; resuming with `Command(resume=...)` injects the human input back into the paused node. HITL requires a checkpointer and stable `thread_id`. References:

- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/graph-api#resume

The local conda environment currently imports `langgraph==1.2.2`, while dependency files still include older `langgraph>=0.2.76` / `<0.3` constraints. Implementation must first verify and align the dependency surface used by `interrupt`, `Command`, and the selected checkpointer.

## Goals

- Add true Human-in-the-loop interrupt/resume to the ecommerce graph.
- Pause immediately after `planner` so a human can approve, edit, supplement, or cancel the query plan before search.
- Pause after `trend`, `competitor`, and `review` complete so a human can approve evidence, mark weak sources, add manual sources, request targeted supplemental search, or cancel before scoring.
- Keep non-HITL mode fully backward compatible and enabled by default.
- Wrap LangGraph checkpoint/resume with a project-level run lifecycle store so the frontend can query pending reviews, decisions, trace, and final outputs without digging through checkpoint internals.
- Make `frontend/ecommerce.html` the single workflow console for start, progress, both interrupts, resume, final results, visual concepts, final review labels, trace, and evaluation summary.
- Preserve existing AgentOps trace and evaluation behavior, extending them with checkpoint and human decision events.

## Non-Goals

- Do not build authentication, multi-user assignment, reviewer roles, or team review queues in this phase.
- Do not migrate the static HTML frontend to Next.js.
- Do not make LLMs interpret arbitrary free-form human instructions in the first version. Human feedback uses structured `approve`, `edit`, `request_more`, and `cancel` decisions.
- Do not remove `frontend/ecommerce-review.html` or `frontend/ecommerce-eval.html` in this phase. They can remain compatibility/dev pages, but they are no longer required for the core workflow.
- Do not make image generation or final visual review a prerequisite for text research completion.

## Proposed Architecture

Use a two-layer design:

```text
LangGraph checkpoint layer
  Owns real pause/resume:
  interrupt(payload) -> checkpoint -> Command(resume=decision) -> continue.

EcomResearcher run lifecycle layer
  Owns product state:
  run_status, pending_review, review_decisions, thread_id, frontend payloads,
  idempotency, and artifact lookup.
```

The graph becomes:

```text
START
  -> planner
  -> plan_review_gate
  -> trend / competitor / review
  -> evidence_review_gate
  -> scoring
  -> writer
  -> quality
  -> END

evidence_review_gate -- request_more --> supplemental_research --> evidence_review_gate
```

`visual` remains a runner post-graph stage for now. It runs only after text graph completion, so evidence review still gates scoring/report/quality before visual concept generation.

Important graph principle:

- Do not place `interrupt()` at the end of `planner_node` or inside the three research nodes.
- Add standalone gate nodes: `plan_review_gate` and `evidence_review_gate`.
- On resume, LangGraph re-enters the interrupted node. Keeping gates small prevents duplicate planner trace, duplicate searches, and duplicate audit writes.

## Configuration

Add request/config fields:

```json
{
  "hitl_enabled": false,
  "hitl_review_mode": "structured",
  "hitl_checkpointer": "memory | sqlite"
}
```

Defaults:

- `hitl_enabled=false`
- `hitl_review_mode="structured"`
- local tests use memory checkpointer
- local demo should use a durable checkpointer, preferably SQLite/file-backed, if available in the installed LangGraph checkpoint packages

The implementation plan must include a pre-flight check:

```text
python -c "from langgraph.types import interrupt, Command"
python -c "import langgraph.checkpoint.memory"
```

If SQLite checkpoint support requires an extra package, add it explicitly and pin it consistently with the installed LangGraph version.

## State Model

Add to `EcommerceResearchState` and `EcommerceGraphState`:

```python
hitl_enabled: bool
hitl_context: dict[str, Any]
```

Initial state:

```json
{
  "hitl_enabled": false,
  "hitl_context": {
    "current_gate": "none",
    "resume_count": 0,
    "plan_review": {},
    "evidence_review": {},
    "supplemental_rounds": []
  }
}
```

`hitl_context` is graph execution state only. Product lifecycle state belongs in run-store metadata.

`EcommerceGraphState` should keep `hitl_context` as a plain channel. Only one gate writes it at a time, and it must not be returned concurrently from the three research branches.

## Run Lifecycle Store

Upgrade `*-run.json` from completed-run metadata to a live run metadata file that can be created and updated while a run is pending.

Recommended schema:

```json
{
  "run_id": "ecom_...",
  "thread_id": "ecom_...",
  "query": "portable blender",
  "target_market": "US",
  "run_status": "running",
  "hitl_enabled": true,
  "created_at_ms": 1782100000000,
  "updated_at_ms": 1782100001000,
  "pending_review": {},
  "review_decisions": [],
  "output_paths": {},
  "evaluation_summary": {},
  "visual_result": {}
}
```

`run_status` values:

```text
running
pending_plan_review
pending_evidence_review
completed
cancelled
failed
```

`thread_id` should default to `run_id` so LangGraph checkpoint identity and run-store identity stay aligned.

Add run-store operations:

```python
create_live_run(metadata)
update_run_status(run_id, status, pending_review=None)
append_review_decision(run_id, decision)
complete_run(run_id, output_paths, evaluation_summary, visual_result)
fail_run(run_id, error)
load_run(run_id)
```

Idempotency:

- `POST /resume` requires `decision_id`.
- If the same `decision_id` was already applied, return the existing run state without resuming the graph again.
- If `gate` does not match the current pending gate, return HTTP 409.
- If `run_status` is not a matching `pending_*` state, return HTTP 409.

## Gate Payloads and Decisions

All gate decisions use a shared envelope:

```json
{
  "decision_id": "uuid-or-client-generated-id",
  "gate": "plan | evidence",
  "decision": "approve | edit | request_more | cancel",
  "payload": {},
  "comment": "optional reviewer comment",
  "reviewer": "local_user"
}
```

### Plan Review Gate

The gate interrupts after `planner` has produced `research_plan` and before any external search begins.

Interrupt payload:

```json
{
  "gate": "plan",
  "title": "Review research plan",
  "allowed_decisions": ["approve", "edit", "request_more", "cancel"],
  "editable_fields": [
    "trend_queries",
    "competitor_queries",
    "review_queries",
    "risk_focus"
  ],
  "research_plan": {
    "trend_queries": [],
    "competitor_queries": [],
    "review_queries": [],
    "risk_focus": [],
    "scoring_dimensions": []
  }
}
```

Decision behavior:

- `approve`: keep current `research_plan`, continue to the three research branches.
- `edit`: validate and replace editable fields in `research_plan`, continue.
- `request_more`: merge `payload.extra_queries` or edited fields into `research_plan`, then interrupt again at the plan gate for confirmation.
- `cancel`: set `hitl_context.current_gate="none"`, mark cancelled, route to `END`.

Plan `request_more` does not rerun `planner`. Planner is deterministic and local, so the gate itself merges human additions.

### Evidence Review Gate

The gate interrupts after `trend`, `competitor`, and `review` complete and before `scoring`.

Interrupt payload:

```json
{
  "gate": "evidence",
  "title": "Review collected evidence",
  "allowed_decisions": ["approve", "edit", "request_more", "cancel"],
  "editable_fields": [
    "invalid_source_ids",
    "manual_sources",
    "notes",
    "extra_queries"
  ],
  "summary": {
    "trend_source_count": 0,
    "competitor_source_count": 0,
    "review_source_count": 0
  },
  "trend_result": {},
  "competitor_result": {},
  "review_result": {}
}
```

Decision behavior:

- `approve`: continue to `scoring`.
- `edit`: apply invalid source labels, manual sources, and notes, then continue to `scoring`.
- `request_more`: store `extra_queries` by lane and route to `supplemental_research`, then return to `evidence_review_gate`.
- `cancel`: route to `END` and mark the run cancelled.

## Supplemental Research

Add a `supplemental_research` node for evidence `request_more`.

Input shape:

```json
{
  "extra_queries": {
    "trend": ["portable blender TikTok trend 2026"],
    "competitor": ["BlendJet competitors price complaints"],
    "review": ["portable blender battery negative reviews"]
  }
}
```

Behavior:

- Only run lanes named in `extra_queries`.
- Use the existing search abstraction, MCP augmentation, budget manager, and source normalization where possible.
- Append new evidence to the existing lane result.
- Add a trace record:

```json
{
  "node": "supplemental_research",
  "agent": "HumanDirectedSupplementalResearchAgent",
  "input_summary": {
    "lanes": ["trend", "review"],
    "query_count": 3
  },
  "output_summary": {
    "added_source_count": 8
  }
}
```

Do not route back to the original `trend`, `competitor`, or `review` nodes for supplemental search. Those nodes consume the original plan and would rerun too much work.

## Graph Routing

Use conditional routing after each gate.

Plan gate routing:

```text
plan_review_gate
  approve/edit  -> trend, competitor, review
  request_more  -> plan_review_gate
  cancel        -> END
```

Evidence gate routing:

```text
evidence_review_gate
  approve/edit  -> scoring
  request_more  -> supplemental_research -> evidence_review_gate
  cancel        -> END
```

Non-HITL mode should bypass gate interrupts:

```text
planner -> plan_review_gate(auto approve) -> trend/competitor/review
...
evidence_review_gate(auto approve) -> scoring
```

This keeps one graph topology while preserving backward compatibility.

## Runner Integration

`run_ecommerce_research()` should support two execution modes:

```python
hitl_enabled: bool = False
resume_command: dict[str, Any] | None = None
thread_id: str | None = None
checkpointer: Any | None = None
```

For a fresh HITL run:

1. Create initial state with `hitl_enabled=True`.
2. Create a live run-store record before graph execution.
3. Compile graph with checkpointer.
4. Invoke graph using `config={"configurable": {"thread_id": run_id}}`.
5. If graph interrupts, update run-store to `pending_plan_review` or `pending_evidence_review` and return the pending payload.
6. If graph completes, continue existing artifact writes, optional visual stage, evaluation summary, and mark `completed`.

For resume:

1. Load run metadata.
2. Validate pending gate and `decision_id`.
3. Append decision before resuming, or write a durable "decision_pending" marker to avoid losing the review if resume fails.
4. Invoke graph with `Command(resume=decision)` and the same `thread_id`.
5. If graph interrupts again, update pending review.
6. If graph completes, write final artifacts and mark completed.

The runner should not duplicate report/evaluation artifact writes while a run is only pending. Final artifacts are written only after graph completion or cancellation/failure metadata is recorded.

## API Design

Extend request model:

```python
hitl_enabled: bool = False
```

`POST /api/ecommerce/research`

- Non-HITL: existing synchronous completed response.
- HITL: starts a run and returns when it reaches the next interrupt or completion.

Pending response:

```json
{
  "run_id": "...",
  "thread_id": "...",
  "run_status": "pending_plan_review",
  "pending_review": {
    "gate": "plan",
    "payload": {}
  },
  "review_decisions": [],
  "agent_trace": []
}
```

Add:

```text
POST /api/ecommerce/runs/{run_id}/resume
```

Request:

```json
{
  "decision_id": "client-generated-id",
  "gate": "plan",
  "decision": "edit",
  "payload": {
    "research_plan": {}
  },
  "comment": "Add TikTok and Reddit queries"
}
```

Responses:

- `pending_plan_review`
- `pending_evidence_review`
- `completed`
- `cancelled`
- `failed`

Errors:

- 404 unknown run
- 409 stale gate, wrong status, or already completed run
- 400 malformed decision payload

`GET /api/ecommerce/runs/{run_id}` should return live and completed run state:

```json
{
  "run_id": "...",
  "run_status": "...",
  "pending_review": {},
  "review_decisions": [],
  "agent_trace": [],
  "evaluation_summary": {},
  "visual_result": {},
  "report": ""
}
```

WebSocket:

- In HITL mode, `/ws/ecommerce` may send progress until `pending_review`, then close.
- First version should prefer REST resume and GET polling over keeping a WebSocket open while a human reviews.
- Events to add:

```text
pending_review
run_resumed
run_cancelled
```

## Single-Page Frontend Design

Hard requirement: every core flow happens inside `frontend/ecommerce.html`.

The page owns:

```text
Start research
Plan Review checkpoint
Progress timeline
Evidence Review checkpoint
Resume/cancel actions
Final score/report/quality
Visual concepts
Final review labels
Eval summary
AgentOps trace
```

Do not require a navigation jump to `frontend/ecommerce-review.html` or `frontend/ecommerce-eval.html` for the main workflow.

UI states:

```text
idle
running
pending_plan_review
pending_evidence_review
completed
cancelled
failed
```

Plan Review panel:

- Editable text areas or list editors for `trend_queries`, `competitor_queries`, `review_queries`, and `risk_focus`.
- Buttons: approve, submit edit, request more, cancel.
- Shows reviewer comment input.

Evidence Review panel:

- Three evidence columns: trend, competitor, review.
- Each source can be marked relevant, weak, irrelevant, duplicate.
- Manual source editor for URL/title/snippet/source_type.
- Extra query editor grouped by lane.
- Buttons: approve, submit edit, request more, cancel.

Completed section:

- Existing score/report/quality UI.
- Visual concepts panel.
- Final post-run labels can be embedded as a compact section on the same page.
- Eval summary and trace table are shown in collapsible sections or tabs inside the same page.

Compatibility pages:

- `frontend/ecommerce-review.html`: may remain as a legacy completed-run review page, but not required for the new workflow.
- `frontend/ecommerce-eval.html`: may remain as a batch eval/dev page, but main run eval summary appears in `ecommerce.html`.

## Evaluation and Trace

Evaluation summary should add:

```json
{
  "hitl_enabled": true,
  "hitl_plan_reviewed": true,
  "hitl_evidence_reviewed": true,
  "hitl_decision_count": 2,
  "hitl_request_more_count": 1,
  "hitl_cancelled": false,
  "supplemental_source_count": 8
}
```

Trace should include gate and supplemental nodes:

```text
planner
plan_review_gate
trend
competitor
review
evidence_review_gate
supplemental_research?   # only request_more
evidence_review_gate?    # second pause
scoring
writer
quality
visual?                  # runner post-graph trace node
```

Gate trace records should not include sensitive reviewer text beyond comments intentionally submitted by the local user. No API keys or signed image URLs should be written to review decisions.

## Error Handling

- Missing or incompatible checkpointer in HITL mode: fail fast with a clear configuration error before starting external searches.
- Interrupt without run-store update: treat as failed run and keep checkpoint thread_id for manual inspection.
- Resume graph failure: keep the decision in `review_decisions`, mark run `failed`, and include redacted error details.
- Cancel: mark run `cancelled`, clear `pending_review`, preserve decisions and partial trace. Do not write final report unless it already exists.
- Stale resume: return 409 and do not invoke graph.
- Duplicate `decision_id`: return current run state and do not invoke graph.

## Testing Strategy

Backend graph tests:

1. `test_plan_gate_interrupts_after_planner`
   - `hitl_enabled=True`
   - graph reaches `pending_plan_review`
   - `research_plan` exists
   - `trend_result`, `competitor_result`, and `review_result` are still empty

2. `test_resume_plan_edit_updates_research_plan`
   - resume with edited plan
   - downstream research uses edited queries

3. `test_evidence_gate_interrupts_after_three_lanes`
   - approve plan
   - trend/competitor/review complete
   - graph pauses before scoring

4. `test_evidence_request_more_runs_supplemental_only`
   - resume evidence with `request_more` for only `review`
   - only review supplemental search runs
   - graph returns to `pending_evidence_review`

5. `test_cancel_stops_run`
   - cancel at either gate
   - no scoring/report/visual generation happens

Run-store/API tests:

- live run metadata is created before HITL graph execution
- pending review is persisted and returned by GET
- resume validates gate/status and returns 409 for stale requests
- duplicate `decision_id` is idempotent
- completed run clears `pending_review` and preserves `review_decisions`

Frontend tests:

- `frontend/ecommerce.html` contains Plan Review and Evidence Review panels.
- `frontend/ecommerce.html` sends `hitl_enabled`.
- `frontend/ecommerce.html` calls `/resume`.
- `frontend/ecommerce.html` handles `pending_plan_review`, `pending_evidence_review`, `completed`, `cancelled`, and `failed`.
- The main workflow does not require `ecommerce-review.html`.

Regression tests:

- Existing non-HITL ecommerce tests continue to pass.
- Existing visual generation flow continues to run only after completed text graph.
- Existing MCP augmentation remains optional and failure-tolerant.

## Acceptance Criteria

- With `hitl_enabled=false`, existing research behavior and API response shape remain backward compatible.
- With `hitl_enabled=true`, the graph pauses immediately after planner and before any external search.
- Plan edits from the frontend change the same run's downstream search behavior.
- The graph pauses after trend/competitor/review and before scoring.
- Evidence review can mark invalid sources, add manual sources, and request targeted supplemental search.
- Evidence `request_more` runs only specified lanes and returns to evidence review.
- All core interrupt, resume, review, and final result actions happen in `frontend/ecommerce.html`.
- Run store exposes `run_status`, `pending_review`, `review_decisions`, `thread_id`, trace, evaluation, report, and visual result.
- Final completed run still writes report, audit, quality, trace, evaluation, human review, run metadata, and optional visual artifacts.
- Human decisions are included in AgentOps trace/evaluation summary without leaking secrets.

## Resume Value

After this upgrade, the project can be described as:

> Built a LangGraph-based ecommerce research agent with checkpoint/resume Human-in-the-loop workflow, supporting query-plan approval, evidence-quality review, human-directed supplemental search, single-page pending-run console, AgentOps trace, eval summaries, optional MCP evidence augmentation, and multimodal visual concept generation.

This is stronger than post-run review because human input changes the same run's execution path before scoring, reporting, and image generation.
