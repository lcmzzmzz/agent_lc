# EcomResearcher Portfolio Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn EcomResearcher into a resume-ready portfolio piece with a strong README, three canonical demo cases, a dedicated evaluation page, and clear engineering signals you can talk about in interviews.

**Architecture:** Keep `multi_agents/ecommerce/` as the source of truth for research runs. Add a thin evaluation layer that records run metrics, a demo export script that materializes repeatable cases, and a presentation layer in the README plus a browser view for comparing runs. Avoid broad refactors; change only the files that explain, measure, or display the existing workflow.

**Tech Stack:** Python, FastAPI, vanilla HTML/CSS/JS, Markdown, pytest, JSON, pathlib.

---

## File Structure

### Create

- `docs/assets/ecommerce/home.png`
- `docs/assets/ecommerce/workflow.png`
- `docs/assets/ecommerce/evaluation.png`
- `docs/ecommerce-portfolio-notes.md`
- `frontend/ecommerce-eval.html`
- `multi_agents/ecommerce/evaluation.py`
- `scripts/export_ecommerce_demo_cases.py`
- `tests/test_ecommerce_evaluation.py`

### Modify

- `README.md`
- `docs/ecommerce-researcher.md`
- `multi_agents/ecommerce/runner.py`
- `tests/test_ecommerce_runner.py`

### Generated artifacts

- `outputs/ecommerce/demo-cases/portable-blender/report.md`
- `outputs/ecommerce/demo-cases/portable-blender/audit.json`
- `outputs/ecommerce/demo-cases/portable-blender/quality.json`
- `outputs/ecommerce/demo-cases/portable-blender/evaluation.json`
- `outputs/ecommerce/demo-cases/pet-water-fountain/report.md`
- `outputs/ecommerce/demo-cases/pet-water-fountain/audit.json`
- `outputs/ecommerce/demo-cases/pet-water-fountain/quality.json`
- `outputs/ecommerce/demo-cases/pet-water-fountain/evaluation.json`
- `outputs/ecommerce/demo-cases/standing-desk/report.md`
- `outputs/ecommerce/demo-cases/standing-desk/audit.json`
- `outputs/ecommerce/demo-cases/standing-desk/quality.json`
- `outputs/ecommerce/demo-cases/standing-desk/evaluation.json`
- `outputs/ecommerce/demo-cases/case-index.json`

---

## Task 1: Rewrite the README as the project homepage

**Files:**
- Modify: `README.md`
- Create: `docs/assets/ecommerce/home.png`
- Create: `docs/assets/ecommerce/workflow.png`
- Create: `docs/assets/ecommerce/evaluation.png`

- [ ] **Step 1: Replace the current top-heavy upstream README with a portfolio-first layout**

Use this structure:

```md
# EcomResearcher

EcomResearcher is a cross-border ecommerce product research agent built on GPT Researcher and LangGraph.

## What it shows
- parallel trend / competitor / review research
- LLM scoring with rule fallback
- WebSocket progress streaming
- audit logs and quality checks

## Demo
![Home](docs/assets/ecommerce/home.png)
![Workflow](docs/assets/ecommerce/workflow.png)
![Evaluation](docs/assets/ecommerce/evaluation.png)

## Quick start
python -m multi_agents.ecommerce --query "portable blender" --market US --platforms amazon,google --depth standard

## Resume-ready highlights
- Multi-agent parallel research
- Real-time WebSocket progress
- Structured evaluation outputs
- Fallback and observability
```

- [ ] **Step 2: Put the project story before the installation wall of text**

Keep the old install instructions, but move them below the new homepage sections. The first screen should explain what the project does, what makes it interesting, and where to click for demo/evaluation.

- [ ] **Step 3: Add the screenshot assets**

Capture three images from the running app and save them exactly as:

```text
docs/assets/ecommerce/home.png
docs/assets/ecommerce/workflow.png
docs/assets/ecommerce/evaluation.png
```

Use the live app and browser screenshots so the images reflect the actual implementation instead of mock art.

- [ ] **Step 4: Verify the homepage text and links**

Run:

```bash
rg -n "EcomResearcher|Resume-ready highlights|Workflow|Evaluation" README.md
```

Expected: the new homepage sections are present and the old deep-installation block is no longer the first thing a visitor sees.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/assets/ecommerce/*.png
git commit -m "docs: turn README into portfolio homepage"
```

---

## Task 2: Add a reusable evaluation summary layer

**Files:**
- Create: `multi_agents/ecommerce/evaluation.py`
- Modify: `multi_agents/ecommerce/runner.py`
- Modify: `tests/test_ecommerce_runner.py`
- Create: `tests/test_ecommerce_evaluation.py`

- [ ] **Step 1: Write the evaluation contract in a new module**

Create a small helper that reads the final state and returns a stable summary:

```python
from __future__ import annotations

from statistics import fmean

def build_evaluation_summary(state: dict) -> dict:
    audit_log = state.get("audit_log", [])
    research_entries = [row for row in audit_log if row.get("agent") != "QualityReviewerAgent"]
    evidence_count = (
        len(state.get("trend_result", {}).get("evidence", []))
        + len(state.get("competitor_result", {}).get("evidence", []))
        + len(state.get("review_result", {}).get("evidence", []))
    )
    fallback_count = sum(1 for row in audit_log if row.get("status") != "success")
    confidence_values = [row.get("confidence", 0.0) for row in research_entries if row.get("confidence") is not None]
    confidence = round(fmean(confidence_values), 2) if confidence_values else 0.0
    duration_ms = sum(int(row.get("duration_ms", 0)) for row in audit_log)
    score = state.get("opportunity_score", {})
    return {
        "overall_score": score.get("overall_score", 0.0),
        "confidence": confidence,
        "evidence_count": evidence_count,
        "fallback_count": fallback_count,
        "duration_ms": duration_ms,
        "recommendation": score.get("recommendation", ""),
        "scored_by": score.get("scored_by", "rule"),
        "quality_passed": state.get("quality_check", {}).get("passed", False),
    }
```

- [ ] **Step 2: Write the summary to disk from the runner**

Update `run_ecommerce_research()` so it also writes:

```text
outputs/ecommerce/<slug>-evaluation.json
```

and adds:

```python
final_state["evaluation_summary"] = evaluation_summary
final_state["output_paths"]["evaluation"] = str(evaluation_path)
```

- [ ] **Step 3: Keep the runner API stable**

Do not change the current `query`, `target_market`, `platforms`, `depth`, `search_fn`, or `llm_fn` parameters. This is a display-and-observability enhancement, not a workflow rewrite.

- [ ] **Step 4: Add tests for the summary math**

Create `tests/test_ecommerce_evaluation.py` with a synthetic state and assert:

```python
def test_build_evaluation_summary_counts_metrics():
    summary = build_evaluation_summary(fake_state)
    assert summary["overall_score"] == 7.8
    assert summary["confidence"] == 0.76
    assert summary["evidence_count"] == 9
    assert summary["fallback_count"] == 1
    assert summary["duration_ms"] == 1820
```

- [ ] **Step 5: Extend the runner test**

Update `tests/test_ecommerce_runner.py` so the end-to-end test also checks:

```python
assert result["evaluation_summary"]["overall_score"] >= 0
assert (tmp_path / "portable-blender-evaluation.json").exists()
```

- [ ] **Step 6: Commit**

```bash
git add multi_agents/ecommerce/evaluation.py multi_agents/ecommerce/runner.py tests/test_ecommerce_evaluation.py tests/test_ecommerce_runner.py
git commit -m "feat(ecommerce): add evaluation summary outputs"
```

---

## Task 3: Export the three canonical demo cases

**Files:**
- Create: `scripts/export_ecommerce_demo_cases.py`
- Modify: `multi_agents/ecommerce/runner.py`
- Generated: `outputs/ecommerce/demo-cases/*`

- [ ] **Step 1: Define the three demo cases explicitly**

Use a tiny case list in the exporter script:

```python
CASES = [
    {"slug": "portable-blender", "query": "portable blender", "target_market": "US", "platforms": ["amazon", "google"], "depth": "standard"},
    {"slug": "pet-water-fountain", "query": "pet water fountain", "target_market": "US", "platforms": ["amazon", "reddit"], "depth": "standard"},
    {"slug": "standing-desk", "query": "standing desk", "target_market": "US", "platforms": ["amazon", "google"], "depth": "deep"},
]
```

- [ ] **Step 2: Add a helper that writes a case folder per run**

The exporter should call `run_ecommerce_research(...)` for each case and write these files into:

```text
outputs/ecommerce/demo-cases/<slug>/
  report.md
  audit.json
  quality.json
  evaluation.json
```

Also write a top-level manifest:

```text
outputs/ecommerce/demo-cases/case-index.json
```

Example manifest shape:

```json
[
  {
    "slug": "portable-blender",
    "title": "Portable Blender",
    "report": "/outputs/ecommerce/demo-cases/portable-blender/report.md",
    "evaluation": "/outputs/ecommerce/demo-cases/portable-blender/evaluation.json"
  }
]
```

- [ ] **Step 3: Make the script reproducible**

Expose a command like:

```bash
py -3.12 scripts/export_ecommerce_demo_cases.py --output-root outputs/ecommerce/demo-cases
```

It should be safe to rerun and overwrite the three demo case folders.

- [ ] **Step 4: Update the README and docs to point at the demo cases**

Add links from the README and `docs/ecommerce-researcher.md` to the generated reports and the evaluation page.

- [ ] **Step 5: Verify the artifacts exist**

Run:

```bash
py -3.12 scripts/export_ecommerce_demo_cases.py --output-root outputs/ecommerce/demo-cases
```

Expected:

```text
outputs/ecommerce/demo-cases/portable-blender/report.md
outputs/ecommerce/demo-cases/pet-water-fountain/report.md
outputs/ecommerce/demo-cases/standing-desk/report.md
outputs/ecommerce/demo-cases/case-index.json
```

- [ ] **Step 6: Commit**

```bash
git add scripts/export_ecommerce_demo_cases.py outputs/ecommerce/demo-cases
git commit -m "feat(ecommerce): export canonical demo cases"
```

---

## Task 4: Build a dedicated evaluation page

**Files:**
- Create: `frontend/ecommerce-eval.html`
- Modify: `docs/ecommerce-researcher.md`

- [ ] **Step 1: Build a small browser page that reads the demo manifest**

Use the existing static frontend mount and fetch the manifest from:

```text
/outputs/ecommerce/demo-cases/case-index.json
```

The page should render a table with:

- `overall_score`
- `confidence`
- `evidence_count`
- `fallback_count`
- `duration_ms`

and a short status badge for `quality_passed`.

Example structure:

```html
<table id="caseTable"></table>
<script>
const manifest = await fetch("/outputs/ecommerce/demo-cases/case-index.json").then(r => r.json());
const rows = await Promise.all(manifest.map(async (item) => {
  const evaluation = await fetch(item.evaluation).then(r => r.json());
  return { ...item, ...evaluation };
}));
document.getElementById("caseTable").innerHTML = rows.map(row => `
  <tr>
    <td>${row.slug}</td>
    <td>${row.overall_score}</td>
    <td>${row.confidence}</td>
    <td>${row.evidence_count}</td>
    <td>${row.fallback_count}</td>
    <td>${row.duration_ms}</td>
  </tr>
`).join("");
</script>
```

- [ ] **Step 2: Make the page feel like an evaluation console**

Add quick navigation to the three demo cases, plus a simple comparison chart or bar strip. The goal is not pretty marketing; it is a clear comparison surface you can show in an interview.

- [ ] **Step 3: Add a docs pointer**

Extend `docs/ecommerce-researcher.md` with a short section that explains:

```md
## Evaluation page
Open `http://localhost:8000/site/ecommerce-eval.html` to compare the three canonical demo cases.
```

- [ ] **Step 4: Verify the page works in the running app**

Run the server and confirm the page loads, the manifest fetch succeeds, and the table shows the three cases.

Expected URL:

```text
http://localhost:8000/site/ecommerce-eval.html
```

- [ ] **Step 5: Commit**

```bash
git add frontend/ecommerce-eval.html docs/ecommerce-researcher.md
git commit -m "feat(ecommerce): add demo evaluation page"
```

---

## Task 5: Add resume-facing notes and lock in the story

**Files:**
- Create: `docs/ecommerce-portfolio-notes.md`
- Modify: `README.md`
- Modify: `docs/ecommerce-researcher.md`

- [ ] **Step 1: Write a short resume bullet bank**

Put the strongest phrasing in `docs/ecommerce-portfolio-notes.md`:

```md
## Resume bullets
- Built a cross-border ecommerce research agent on GPT Researcher and LangGraph with parallel trend, competitor, and review analysis.
- Added WebSocket-based progress streaming, audit logs, and fallback scoring for a stable end-to-end workflow.
- Produced structured evaluation outputs with score, confidence, evidence count, fallback count, and runtime.
- Packaged canonical demo cases and a dedicated comparison page for portfolio-ready presentation.
```

- [ ] **Step 2: Keep the story consistent across README and docs**

The README should stay concise and the doc page should hold the longer explanation. Both should point at the same demo cases and evaluation page so the story is easy to repeat in an interview.

- [ ] **Step 3: Run a final verification pass**

Run:

```bash
py -3.12 -m pytest tests/test_ecommerce_evaluation.py tests/test_ecommerce_runner.py -q
rg -n "evidence_count|fallback_count|ecommerce-eval|Resume bullets" README.md docs/ecommerce-researcher.md docs/ecommerce-portfolio-notes.md
```

Expected: the new metrics and resume language are present, and the tests stay green.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/ecommerce-researcher.md docs/ecommerce-portfolio-notes.md
git commit -m "docs: add portfolio notes and resume highlights"
```

---

## Self-Review

### Spec coverage
- README as homepage: Task 1
- Three demo cases with saved artifacts: Task 3
- Evaluation page and metrics: Tasks 2 and 4
- Engineering signals for resume: Task 5

### Placeholder scan
- No TBD/TODO placeholders.
- Demo cases, output paths, and verification commands are explicit.

### Type consistency
- `evaluation_summary` keys are consistent across runner, exporter, page, and tests.
- Demo case slugs are stable: `portable-blender`, `pet-water-fountain`, `standing-desk`.
- Output layout is consistent across `report.md`, `audit.json`, `quality.json`, and `evaluation.json`.
