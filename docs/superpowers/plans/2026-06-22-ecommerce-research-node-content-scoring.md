# Ecommerce Research Node Content Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the ecommerce trend, competitor, and review research nodes so their scores come from content-aware LLM JSON analysis when available, while preserving existing rule fallbacks and downstream score fields.

**Architecture:** Add a small shared scoring helper module for source formatting, score coercion, confidence coercion, and list extraction. Then update each node independently to request structured JSON from the LLM, apply safe field-level fallbacks, and mark `scored_by`. Existing search, review scraping, audit logging, and downstream opportunity scoring remain intact.

**Tech Stack:** Python async agents, pytest with `pytest.mark.asyncio`, injected fake `search_fn` and `llm_fn`, existing `multi_agents.ecommerce.llm_helper.llm_json`.

## Global Constraints

- `trend_score` means market trend strength, not source volume.
- `competition_score` means ease of competitive entry; higher means easier to enter, not more competition.
- `pain_point_score` means actionable unmet-need opportunity, not raw complaint count.
- `confidence` means how reliable each node judgment is.
- `source_count` remains raw evidence quantity for audit and fallback logic.
- Preserve existing rule fallback behavior and mark rule fallbacks with `scored_by="rule"`.
- Do not change final opportunity scoring weights.
- Do not add keyword sentiment scoring as a fallback.
- Do not require frontend or report rendering changes.
- Do not replace Apify review scraping or fallback web review extraction.

---

## File Structure

- Create `multi_agents/ecommerce/agents/content_scoring.py`
  - Shared helpers for formatting sources/reviews for prompts, coercing score/confidence values, extracting string lists, and producing rule fallback rationales.
- Modify `multi_agents/ecommerce/agents/trend_researcher.py`
  - Replace text-only LLM summary path with structured LLM trend scoring.
  - Preserve current source-count fallback for no LLM or invalid JSON.
- Modify `multi_agents/ecommerce/agents/competitor_analyzer.py`
  - Replace text-only LLM summary path with structured competitor scoring.
  - Preserve price extraction, competitor extraction fallback, and current rule score fallback.
- Modify `multi_agents/ecommerce/agents/review_insight.py`
  - Extend existing JSON LLM pain-point summarization into content scoring.
  - Preserve Apify/web fallback scraping and raw-pain-point fallback.
- Modify `tests/test_ecommerce_agents.py`
  - Add focused tests for LLM-scored positive/negative cases and rule fallback markers.

---

### Task 1: Shared Content Scoring Helpers

**Files:**
- Create: `multi_agents/ecommerce/agents/content_scoring.py`
- Test: `tests/test_ecommerce_agents.py`

**Interfaces:**
- Consumes: `multi_agents.ecommerce.llm_helper.clamp`
- Produces:
  - `format_sources_for_prompt(sources: list[dict], *, limit: int = 8, max_chars: int = 3000) -> str`
  - `format_review_texts_for_prompt(texts: list[str], *, limit: int = 12, max_chars: int = 3000) -> str`
  - `coerce_score(data: dict | None, key: str, fallback: float) -> float`
  - `coerce_confidence(data: dict | None, fallback: float) -> float`
  - `coerce_string_list(value, *, limit: int) -> list[str]`
  - `coerce_competitors(value, fallback: list[dict[str, str]], *, limit: int = 3) -> list[dict[str, str]]`
  - `source_count_confidence(source_count: int, *, base: float = 0.35, step: float = 0.1) -> float`
  - `rule_rationale(label: str) -> str`

- [ ] **Step 1: Write failing helper tests**

Append these tests near the top of `tests/test_ecommerce_agents.py`, after the fake LLM helpers:

```python
def test_content_scoring_helpers_coerce_scores_and_lists():
    from multi_agents.ecommerce.agents.content_scoring import (
        coerce_confidence,
        coerce_score,
        coerce_string_list,
        source_count_confidence,
    )

    data = {"score": "8.7", "confidence": "0.95", "items": ["a", "", 3]}

    assert coerce_score(data, "score", 5.0) == 8.7
    assert coerce_score({"score": "bad"}, "score", 5.0) == 5.0
    assert coerce_confidence(data, 0.4) == 0.9
    assert coerce_confidence({"confidence": "bad"}, 0.4) == 0.4
    assert coerce_string_list(data["items"], limit=3) == ["a", "3"]
    assert source_count_confidence(6) == 0.9


def test_content_scoring_helpers_format_sources_for_prompt():
    from multi_agents.ecommerce.agents.content_scoring import format_sources_for_prompt

    text = format_sources_for_prompt(
        [
            {
                "title": "Market report",
                "url": "https://example.com/report",
                "snippet": "Demand is growing",
                "content": "More context",
            }
        ],
        limit=1,
        max_chars=200,
    )

    assert "Market report" in text
    assert "Demand is growing" in text
    assert "https://example.com/report" in text
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_content_scoring_helpers_coerce_scores_and_lists tests/test_ecommerce_agents.py::test_content_scoring_helpers_format_sources_for_prompt -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'multi_agents.ecommerce.agents.content_scoring'`.

- [ ] **Step 3: Create helper module**

Create `multi_agents/ecommerce/agents/content_scoring.py`:

```python
"""Shared helpers for ecommerce research-node content scoring."""

from __future__ import annotations

from typing import Any

from multi_agents.ecommerce.llm_helper import clamp


def format_sources_for_prompt(
    sources: list[dict[str, Any]], *, limit: int = 8, max_chars: int = 3000
) -> str:
    lines: list[str] = []
    for source in sources[:limit]:
        title = str(source.get("title") or "Untitled source")
        url = str(source.get("url") or "")
        snippet = str(source.get("snippet") or "")
        content = str(source.get("content") or "")
        lines.append(f"- title: {title}\n  url: {url}\n  text: {snippet} {content}")
    return "\n".join(lines)[:max_chars]


def format_review_texts_for_prompt(
    texts: list[str], *, limit: int = 12, max_chars: int = 3000
) -> str:
    return "\n".join(f"- {text}" for text in texts[:limit] if text)[:max_chars]


def coerce_score(data: dict | None, key: str, fallback: float) -> float:
    if not isinstance(data, dict):
        return fallback
    try:
        return clamp(data.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def coerce_confidence(data: dict | None, fallback: float) -> float:
    if not isinstance(data, dict):
        return fallback
    try:
        value = float(data.get("confidence", fallback))
    except (TypeError, ValueError):
        return fallback
    return round(max(0.0, min(0.9, value)), 2)


def coerce_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def coerce_competitors(
    value: Any, fallback: list[dict[str, str]], *, limit: int = 3
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return fallback
    competitors: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        positioning = str(item.get("positioning") or "").strip()
        if name:
            competitors.append({"name": name[:80], "positioning": positioning[:160]})
        if len(competitors) >= limit:
            break
    return competitors or fallback


def source_count_confidence(
    source_count: int, *, base: float = 0.35, step: float = 0.1
) -> float:
    return round(min(0.9, base + source_count * step), 2)


def rule_rationale(label: str) -> str:
    return f"LLM unavailable or returned invalid JSON; {label} estimated from simple rule fallback."
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_content_scoring_helpers_coerce_scores_and_lists tests/test_ecommerce_agents.py::test_content_scoring_helpers_format_sources_for_prompt -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add multi_agents/ecommerce/agents/content_scoring.py tests/test_ecommerce_agents.py
git commit -m "feat(ecommerce): add content scoring helpers"
```

---

### Task 2: TrendResearchAgent Structured Scoring

**Files:**
- Modify: `multi_agents/ecommerce/agents/trend_researcher.py`
- Test: `tests/test_ecommerce_agents.py`

**Interfaces:**
- Consumes:
  - `llm_json(llm_fn, TREND_RESEARCHER_SYSTEM_PROMPT, user) -> tuple[dict | None, bool]`
  - Helpers from `multi_agents.ecommerce.agents.content_scoring`
- Produces:
  - `trend_result.scored_by: "llm" | "rule"`
  - `trend_result.negative_signals: list[str]`
  - `trend_result.scoring_rationale: str`

- [ ] **Step 1: Write failing trend scoring tests**

Append these tests after `test_run_trend_research_summary_uses_llm`:

```python
@pytest.mark.asyncio
async def test_run_trend_research_uses_llm_json_score_for_negative_sources():
    async def negative_search(query: str, max_results: int):
        return [
            {
                "title": f"Weak demand {query}",
                "href": f"https://example.com/weak-{query.replace(' ', '-')}",
                "body": "Retailers report slowing demand and negative consumer interest.",
            }
        ]

    async def trend_llm(system: str, user: str) -> str:
        return (
            '{"summary":"公开资料显示需求走弱。","trend_score":2.5,'
            '"confidence":0.72,"key_findings":["需求走弱"],'
            '"negative_signals":["负面报道较多"],'
            '"scoring_rationale":"来源内容主要显示需求下降。"}'
        )

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_trend_research(state, search_fn=negative_search, llm_fn=trend_llm)

    result = updated["trend_result"]
    assert result["scored_by"] == "llm"
    assert result["summary_source"] == "llm"
    assert result["trend_score"] == 2.5
    assert result["confidence"] == 0.72
    assert result["negative_signals"] == ["负面报道较多"]


@pytest.mark.asyncio
async def test_run_trend_research_invalid_llm_json_marks_rule_fallback():
    async def bad_json_llm(system: str, user: str) -> str:
        return "not json"

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_trend_research(state, search_fn=fake_search, llm_fn=bad_json_llm)

    result = updated["trend_result"]
    assert result["scored_by"] == "rule"
    assert result["summary_source"] == "template"
    assert result["trend_score"] == 7.0
    assert "fallback" in result["scoring_rationale"]
```

- [ ] **Step 2: Run trend tests to verify they fail**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_run_trend_research_uses_llm_json_score_for_negative_sources tests/test_ecommerce_agents.py::test_run_trend_research_invalid_llm_json_marks_rule_fallback -v
```

Expected: FAIL because `trend_result.scored_by`, `negative_signals`, and structured LLM score application do not exist yet.

- [ ] **Step 3: Update trend imports and replace text LLM helper**

In `multi_agents/ecommerce/agents/trend_researcher.py`, change the LLM import and add helper imports:

```python
from multi_agents.ecommerce.llm_helper import LlmFn, llm_json
from multi_agents.ecommerce.agents.content_scoring import (
    coerce_confidence,
    coerce_score,
    coerce_string_list,
    format_sources_for_prompt,
    rule_rationale,
    source_count_confidence,
)
```

Replace `_llm_trend_summary` with:

```python
async def _llm_trend_score(
    llm_fn: LlmFn | None, query: str, market: str, sources: list
) -> tuple[dict | None, bool]:
    if not llm_fn or not sources:
        return None, False
    text = format_sources_for_prompt(sources)
    user = (
        f"品类：{query}（市场：{market}）\n"
        f"以下是与该品类市场趋势相关的公开资料：\n{text}\n"
        "请只返回 JSON 对象："
        '{"summary":"2-4句中文总结","trend_score":0-10,"confidence":0-0.9,'
        '"key_findings":["中文发现"],"negative_signals":["中文负面信号"],'
        '"scoring_rationale":"中文评分理由"}。'
        "trend_score 只评价市场趋势强弱，不评价竞争、利润或进入难度。"
        "如果资料主要显示需求下降、负面报道或增长乏力，请降低 trend_score。"
        "如果证据稀疏、矛盾或相关性弱，请降低 confidence。"
    )
    return await llm_json(llm_fn, TREND_RESEARCHER_SYSTEM_PROMPT, user)
```

- [ ] **Step 4: Apply structured trend result in the main function**

Inside `run_trend_research`, after `source_count = len(limited_sources)`, replace the old `confidence`, `trend_score`, `llm_summary`, and `summary` block with:

```python
        rule_confidence = source_count_confidence(source_count)
        rule_trend_score = 7.0 if source_count >= 3 else 5.5

        llm_data, used_llm = await _llm_trend_score(
            llm_fn, state["query"], state["target_market"], limited_sources
        )
        if llm_fn and not used_llm:
            logger.warning("[Trend] LLM scoring 失败，回退规则评分")

        summary = (
            str(llm_data.get("summary")).strip()
            if used_llm and llm_data and llm_data.get("summary")
            else _TEMPLATE_SUMMARY.format(query=state["query"], market=state["target_market"])
        )
        trend_score = (
            coerce_score(llm_data, "trend_score", rule_trend_score)
            if used_llm
            else rule_trend_score
        )
        confidence = (
            coerce_confidence(llm_data, rule_confidence)
            if used_llm
            else rule_confidence
        )
        key_findings = (
            coerce_string_list(llm_data.get("key_findings"), limit=5)
            if used_llm and llm_data
            else [
                "公开资料显示该品类存在搜索和评测内容。",
                "需要结合平台真实销量和供应链成本进一步验证。",
            ]
        )
        negative_signals = (
            coerce_string_list(llm_data.get("negative_signals"), limit=5)
            if used_llm and llm_data
            else []
        )
        scoring_rationale = (
            str(llm_data.get("scoring_rationale")).strip()
            if used_llm and llm_data and llm_data.get("scoring_rationale")
            else rule_rationale("trend_score")
        )
```

Then update the `state["trend_result"]` dict to use:

```python
            "summary": summary,
            "summary_source": "llm" if used_llm else "template",
            "trend_score": trend_score,
            "key_findings": key_findings,
            "negative_signals": negative_signals,
            "scoring_rationale": scoring_rationale,
            "scored_by": "llm" if used_llm else "rule",
            "evidence": limited_sources,
            "confidence": confidence,
```

In the exception fallback dict, add:

```python
            "negative_signals": [],
            "scoring_rationale": "Trend research failed before content scoring.",
            "scored_by": "rule",
```

- [ ] **Step 5: Run trend tests and existing trend tests**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_run_trend_research_returns_result tests/test_ecommerce_agents.py::test_run_trend_research_summary_uses_llm tests/test_ecommerce_agents.py::test_run_trend_research_uses_llm_json_score_for_negative_sources tests/test_ecommerce_agents.py::test_run_trend_research_invalid_llm_json_marks_rule_fallback tests/test_ecommerce_agents.py::test_run_trend_research_degrades_on_search_failure -v
```

Expected: PASS. If `test_run_trend_research_summary_uses_llm` fails because it uses text instead of JSON, change `fake_llm_text` in that test only to a JSON-returning fake or update the assertion to check rule fallback; keep a dedicated JSON success test as the content-scoring path.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add multi_agents/ecommerce/agents/trend_researcher.py tests/test_ecommerce_agents.py
git commit -m "feat(ecommerce): score trends from LLM content JSON"
```

---

### Task 3: CompetitorAnalysisAgent Structured Scoring

**Files:**
- Modify: `multi_agents/ecommerce/agents/competitor_analyzer.py`
- Test: `tests/test_ecommerce_agents.py`

**Interfaces:**
- Consumes:
  - `llm_json(llm_fn, COMPETITOR_ANALYZER_SYSTEM_PROMPT, user)`
  - Helpers from `content_scoring.py`
- Produces:
  - `competitor_result.scored_by: "llm" | "rule"`
  - `competitor_result.competitive_signals: list[str]`
  - `competitor_result.entry_barriers: list[str]`
  - `competitor_result.scoring_rationale: str`

- [ ] **Step 1: Write failing competitor tests**

Append these tests after `test_run_competitor_analysis_returns_result`:

```python
@pytest.mark.asyncio
async def test_run_competitor_analysis_llm_lowers_score_for_strong_incumbents():
    async def competitor_llm(system: str, user: str) -> str:
        return (
            '{"summary":"头部品牌强，价格竞争明显。","competition_score":2.0,'
            '"confidence":0.7,'
            '"competitors":[{"name":"Dominant Brand","positioning":"头部品牌"}],'
            '"competitive_signals":["头部品牌占据主要曝光"],'
            '"entry_barriers":["价格战明显"],'
            '"differentiation_opportunities":["避开低价同质化"],'
            '"scoring_rationale":"强势竞品和价格压缩使进入难度较高。"}'
        )

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_competitor_analysis(state, search_fn=fake_search, llm_fn=competitor_llm)

    result = updated["competitor_result"]
    assert result["scored_by"] == "llm"
    assert result["competition_score"] == 2.0
    assert result["entry_barriers"] == ["价格战明显"]
    assert result["competitors"][0]["name"] == "Dominant Brand"


@pytest.mark.asyncio
async def test_run_competitor_analysis_invalid_llm_json_marks_rule_fallback():
    async def bad_json_llm(system: str, user: str) -> str:
        return "not json"

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_competitor_analysis(state, search_fn=fake_search, llm_fn=bad_json_llm)

    result = updated["competitor_result"]
    assert result["scored_by"] == "rule"
    assert result["competition_score"] == 6.0
    assert "fallback" in result["scoring_rationale"]
```

- [ ] **Step 2: Run competitor tests to verify they fail**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_run_competitor_analysis_llm_lowers_score_for_strong_incumbents tests/test_ecommerce_agents.py::test_run_competitor_analysis_invalid_llm_json_marks_rule_fallback -v
```

Expected: FAIL because `competitor_result.scored_by`, `entry_barriers`, and structured score application do not exist yet.

- [ ] **Step 3: Update competitor imports and structured LLM helper**

In `multi_agents/ecommerce/agents/competitor_analyzer.py`, change imports:

```python
from multi_agents.ecommerce.llm_helper import LlmFn, llm_json
from multi_agents.ecommerce.agents.content_scoring import (
    coerce_competitors,
    coerce_confidence,
    coerce_score,
    coerce_string_list,
    format_sources_for_prompt,
    rule_rationale,
    source_count_confidence,
)
```

Replace `_llm_competitor_summary` with:

```python
async def _llm_competitor_score(
    llm_fn: LlmFn | None, query: str, market: str, sources: list, price_range: str
) -> tuple[dict | None, bool]:
    if not llm_fn or not sources:
        return None, False
    text = format_sources_for_prompt(sources)
    user = (
        f"品类：{query}（市场：{market}）\n初步价格区间：{price_range}\n"
        f"以下是与该品类竞品相关的公开资料：\n{text}\n"
        "请只返回 JSON 对象："
        '{"summary":"2-4句中文总结","competition_score":0-10,"confidence":0-0.9,'
        '"competitors":[{"name":"竞品名","positioning":"定位"}],'
        '"competitive_signals":["中文竞争信号"],"entry_barriers":["中文进入障碍"],'
        '"differentiation_opportunities":["中文差异化机会"],'
        '"scoring_rationale":"中文评分理由"}。'
        "competition_score 越高代表越容易切入，不代表竞争越强。"
        "如果资料显示头部品牌强、价格战、同质化或差异化空间小，请降低 competition_score。"
    )
    return await llm_json(llm_fn, COMPETITOR_ANALYZER_SYSTEM_PROMPT, user)
```

- [ ] **Step 4: Apply structured competitor result in the main function**

After the fallback `competitors` and `differentiation_opportunities` lists are built, insert:

```python
        rule_confidence = source_count_confidence(source_count)
        rule_competition_score = 6.0 if source_count >= 3 else 5.0
        llm_data, used_llm = await _llm_competitor_score(
            llm_fn, state["query"], state["target_market"], limited_sources, price_range
        )
        if llm_fn and not used_llm:
            logger.warning("[Competitor] LLM scoring 失败，回退规则评分")

        summary = (
            str(llm_data.get("summary")).strip()
            if used_llm and llm_data and llm_data.get("summary")
            else _TEMPLATE_SUMMARY
        )
        competition_score = (
            coerce_score(llm_data, "competition_score", rule_competition_score)
            if used_llm
            else rule_competition_score
        )
        confidence = (
            coerce_confidence(llm_data, rule_confidence)
            if used_llm
            else rule_confidence
        )
        competitors = (
            coerce_competitors(llm_data.get("competitors"), competitors)
            if used_llm and llm_data
            else competitors
        )
        competitive_signals = (
            coerce_string_list(llm_data.get("competitive_signals"), limit=5)
            if used_llm and llm_data
            else []
        )
        entry_barriers = (
            coerce_string_list(llm_data.get("entry_barriers"), limit=5)
            if used_llm and llm_data
            else []
        )
        differentiation_opportunities = (
            coerce_string_list(llm_data.get("differentiation_opportunities"), limit=5)
            if used_llm and llm_data and llm_data.get("differentiation_opportunities")
            else differentiation_opportunities
        )
        scoring_rationale = (
            str(llm_data.get("scoring_rationale")).strip()
            if used_llm and llm_data and llm_data.get("scoring_rationale")
            else rule_rationale("competition_score")
        )
```

Remove the earlier text-summary LLM block so there is only one LLM call in this agent. Update `state["competitor_result"]` to include:

```python
            "summary_source": "llm" if used_llm else "template",
            "competition_score": competition_score,
            "competitive_signals": competitive_signals,
            "entry_barriers": entry_barriers,
            "scoring_rationale": scoring_rationale,
            "scored_by": "llm" if used_llm else "rule",
            "confidence": confidence,
```

In the exception fallback dict, add:

```python
            "competitive_signals": [],
            "entry_barriers": [],
            "scoring_rationale": "Competitor analysis failed before content scoring.",
            "scored_by": "rule",
```

- [ ] **Step 5: Run competitor tests**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_run_competitor_analysis_summary_uses_llm tests/test_ecommerce_agents.py::test_run_competitor_analysis_returns_result tests/test_ecommerce_agents.py::test_run_competitor_analysis_llm_lowers_score_for_strong_incumbents tests/test_ecommerce_agents.py::test_run_competitor_analysis_invalid_llm_json_marks_rule_fallback -v
```

Expected: PASS. If the old summary text test fails, update its fake LLM to return the JSON shape from this task and keep the assertion that `summary_source == "llm"`.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add multi_agents/ecommerce/agents/competitor_analyzer.py tests/test_ecommerce_agents.py
git commit -m "feat(ecommerce): score competitors from LLM content JSON"
```

---

### Task 4: ReviewInsightAgent Structured Pain-Point Scoring

**Files:**
- Modify: `multi_agents/ecommerce/agents/review_insight.py`
- Test: `tests/test_ecommerce_agents.py`

**Interfaces:**
- Consumes:
  - Existing `ReviewSource.scrape(...)`
  - Existing raw `ReviewItem.review_text`
  - Helpers from `content_scoring.py`
- Produces:
  - `review_result.scored_by: "llm" | "rule"`
  - `review_result.actionable_pain_points: list[str]`
  - `review_result.structural_risks: list[str]`
  - `review_result.scoring_rationale: str`

- [ ] **Step 1: Write failing review tests**

Append these tests after `test_run_review_insight_translates_to_chinese_with_llm`:

```python
@pytest.mark.asyncio
async def test_run_review_insight_llm_scores_structural_risks_low():
    async def review_llm(system: str, user: str) -> str:
        if "Amazon 搜索关键词" in system:
            return "portable blender"
        return (
            '{"summary":"评论主要集中在安全和耐用风险。",'
            '"pain_points":["电池过热","刀片安全隐患","漏液"],'
            '"pain_point_score":3.0,"confidence":0.66,'
            '"actionable_pain_points":["改善密封"],'
            '"structural_risks":["安全风险较高","耐用性问题难以快速解决"],'
            '"scoring_rationale":"痛点多但主要是结构性风险，因此机会分较低。"}'
        )

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_review_insight(state, search_fn=fake_search, llm_fn=review_llm)

    result = updated["review_result"]
    assert result["scored_by"] == "llm"
    assert result["pain_point_score"] == 3.0
    assert result["structural_risks"] == ["安全风险较高", "耐用性问题难以快速解决"]
    assert result["pain_points_language"] == "zh"


@pytest.mark.asyncio
async def test_run_review_insight_invalid_llm_json_marks_rule_fallback():
    async def bad_json_llm(system: str, user: str) -> str:
        return "portable blender" if "Amazon 搜索关键词" in system else "not json"

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_review_insight(state, search_fn=fake_search, llm_fn=bad_json_llm)

    result = updated["review_result"]
    assert result["scored_by"] == "rule"
    assert result["pain_point_score"] >= 0
    assert "fallback" in result["scoring_rationale"]
```

- [ ] **Step 2: Run review tests to verify they fail**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_run_review_insight_llm_scores_structural_risks_low tests/test_ecommerce_agents.py::test_run_review_insight_invalid_llm_json_marks_rule_fallback -v
```

Expected: FAIL because `review_result.scored_by`, `structural_risks`, and structured pain-point scoring are not applied yet.

- [ ] **Step 3: Add structured review scoring helper**

In `multi_agents/ecommerce/agents/review_insight.py`, add imports:

```python
from multi_agents.ecommerce.agents.content_scoring import (
    coerce_confidence,
    coerce_score,
    coerce_string_list,
    format_review_texts_for_prompt,
    rule_rationale,
)
```

Replace `_summarize_pain_points_zh` with:

```python
async def _score_pain_points_zh(
    llm_fn: LlmFn | None, texts: list[str]
) -> tuple[dict | None, bool]:
    if not llm_fn or not texts:
        return None, False
    review_text = format_review_texts_for_prompt(texts)
    user = (
        "以下是从公开资料/平台抓取的用户评论与反馈（可能为英文）：\n"
        + review_text
        + "\n请只返回 JSON 对象："
        '{"summary":"2-4句中文总结","pain_points":["中文痛点"],'
        '"pain_point_score":0-10,"confidence":0-0.9,'
        '"actionable_pain_points":["中文可转化机会"],'
        '"structural_risks":["中文结构性风险"],'
        '"scoring_rationale":"中文评分理由"}。'
        "pain_point_score 越高代表痛点越具体、频繁、可解决，越能转化为产品或 Listing 改进机会。"
        "不要因为投诉数量多就自动给高分；如果主要是安全、合规、耐用或品类结构性风险，请降低分数。"
    )
    return await llm_json(llm_fn, REVIEW_INSIGHT_SYSTEM_PROMPT, user)
```

- [ ] **Step 4: Apply structured review result in the main function**

Replace:

```python
    zh_pain_points, used_llm = await _summarize_pain_points_zh(llm_fn, raw_texts)
    final_pain_points = zh_pain_points or raw_texts
```

with:

```python
    llm_data, used_llm = await _score_pain_points_zh(llm_fn, raw_texts)
    zh_pain_points = (
        coerce_string_list(llm_data.get("pain_points"), limit=6)
        if used_llm and llm_data
        else []
    )
    final_pain_points = zh_pain_points or raw_texts
```

Before `state["review_result"] = {`, add:

```python
    rule_pain_point_score = 8.0 if len(final_pain_points) >= 3 else 5.5
    rule_confidence = round(min(0.9, 0.3 + len(final_pain_points) * 0.08), 2)
    pain_point_score = (
        coerce_score(llm_data, "pain_point_score", rule_pain_point_score)
        if used_llm
        else rule_pain_point_score
    )
    confidence = (
        coerce_confidence(llm_data, rule_confidence)
        if used_llm
        else rule_confidence
    )
    summary = (
        str(llm_data.get("summary")).strip()
        if used_llm and llm_data and llm_data.get("summary")
        else "基于多源评论/反馈归纳用户痛点；评论来源见 review_source 字段。"
    )
    actionable_pain_points = (
        coerce_string_list(llm_data.get("actionable_pain_points"), limit=5)
        if used_llm and llm_data
        else final_pain_points[:5]
    )
    structural_risks = (
        coerce_string_list(llm_data.get("structural_risks"), limit=5)
        if used_llm and llm_data
        else []
    )
    scoring_rationale = (
        str(llm_data.get("scoring_rationale")).strip()
        if used_llm and llm_data and llm_data.get("scoring_rationale")
        else rule_rationale("pain_point_score")
    )
```

Update `state["review_result"]` fields:

```python
        "summary": summary,
        "pain_point_score": pain_point_score,
        "actionable_pain_points": actionable_pain_points,
        "structural_risks": structural_risks,
        "scoring_rationale": scoring_rationale,
        "scored_by": "llm" if used_llm else "rule",
        "confidence": confidence,
```

Keep existing `opportunity_insights`; set it from `actionable_pain_points` when available:

```python
        "opportunity_insights": actionable_pain_points
        or [
            "将高频抱怨点转化为产品改进点。",
            "在 Listing 中明确使用场景和限制，降低预期偏差。",
        ],
```

- [ ] **Step 5: Run review tests**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_run_review_insight_returns_pain_points tests/test_ecommerce_agents.py::test_run_review_insight_translates_to_chinese_with_llm tests/test_ecommerce_agents.py::test_run_review_insight_llm_scores_structural_risks_low tests/test_ecommerce_agents.py::test_run_review_insight_invalid_llm_json_marks_rule_fallback -v
```

Expected: PASS. If keyword translation consumes the fake JSON intended for scoring, make the fake LLM return `"portable blender"` when the system prompt contains `"Amazon 搜索关键词"` and the scoring JSON otherwise, as shown in Step 1.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add multi_agents/ecommerce/agents/review_insight.py tests/test_ecommerce_agents.py
git commit -m "feat(ecommerce): score review pain points from LLM JSON"
```

---

### Task 5: Downstream Regression and Documentation Sync

**Files:**
- Modify: `docs/ecommerce-architecture-guide.md`
- Test: `tests/test_ecommerce_agents.py`

**Interfaces:**
- Consumes:
  - Existing `run_opportunity_scoring(build_ready_state())`
  - New `scored_by` fields from research nodes
- Produces:
  - Documentation that describes content-aware scoring and rule fallbacks for all three nodes.

- [ ] **Step 1: Add downstream schema regression test**

Append this test after `test_run_opportunity_scoring_rule_mode`:

```python
@pytest.mark.asyncio
async def test_opportunity_scoring_accepts_content_scored_research_nodes():
    state = build_ready_state()
    state["trend_result"]["scored_by"] = "llm"
    state["trend_result"]["negative_signals"] = ["需求波动"]
    state["trend_result"]["scoring_rationale"] = "趋势分来自内容分析。"
    state["competitor_result"]["scored_by"] = "llm"
    state["competitor_result"]["entry_barriers"] = ["头部品牌强"]
    state["competitor_result"]["scoring_rationale"] = "竞争分代表切入容易度。"
    state["review_result"]["scored_by"] = "llm"
    state["review_result"]["structural_risks"] = ["安全风险"]
    state["review_result"]["scoring_rationale"] = "痛点分代表可转化机会。"

    updated = await run_opportunity_scoring(state)

    assert updated["opportunity_score"]["overall_score"] > 0
    assert updated["opportunity_score"]["trend_score"] == state["trend_result"]["trend_score"]
    assert updated["opportunity_score"]["competition_score"] == state["competitor_result"]["competition_score"]
    assert updated["opportunity_score"]["pain_point_score"] == state["review_result"]["pain_point_score"]
```

- [ ] **Step 2: Run downstream regression test**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py::test_opportunity_scoring_accepts_content_scored_research_nodes -v
```

Expected: PASS.

- [ ] **Step 3: Update architecture guide scoring sections**

In `docs/ecommerce-architecture-guide.md`, update the sections that currently describe these rules:

```markdown
**TrendResearchAgent scoring**: LLM available -> score from source content and return `scored_by="llm"`, `negative_signals`, and `scoring_rationale`; LLM unavailable or invalid JSON -> existing source-count rule fallback with `scored_by="rule"`.

**CompetitorAnalysisAgent scoring**: `competition_score` means ease of competitive entry. LLM available -> score from competitor strength, price crowding, barriers, and differentiation space. LLM unavailable or invalid JSON -> existing source-count rule fallback marked as `scored_by="rule"`.

**ReviewInsightAgent scoring**: `pain_point_score` means actionable unmet-need opportunity. LLM available -> score from pain-point frequency, specificity, solvability, and structural risks. LLM unavailable or invalid JSON -> existing pain-point-count rule fallback marked as `scored_by="rule"`.
```

Keep existing audit-field descriptions and add `scored_by` as an optional result field rather than an audit baseline field.

- [ ] **Step 4: Run focused ecommerce test suite**

Run:

```bash
python -m pytest tests/test_ecommerce_agents.py tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py -v
```

Expected: PASS.

- [ ] **Step 5: Run final status check**

Run:

```bash
git status --short
```

Expected: Only files intentionally modified by this plan are shown, plus any unrelated pre-existing worktree changes that were already present before implementation.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add docs/ecommerce-architecture-guide.md tests/test_ecommerce_agents.py
git commit -m "docs(ecommerce): document content-aware research scoring"
```

---

## Self-Review

- Spec coverage: Task 2 covers trend content scoring, negative signals, confidence, and rule fallback. Task 3 covers competitor entry-ease scoring, barriers, confidence, and rule fallback. Task 4 covers actionable pain-point scoring, structural risks, confidence, and rule fallback. Task 5 covers downstream compatibility and docs.
- Placeholder scan: This plan contains concrete file paths, exact function names, test snippets, commands, expected outcomes, and commit commands.
- Type consistency: All helper signatures introduced in Task 1 are consumed with the same names in Tasks 2-4. All new result fields match the spec: `scored_by`, `scoring_rationale`, `negative_signals`, `competitive_signals`, `entry_barriers`, `actionable_pain_points`, and `structural_risks`.
