# Ecommerce Trend Scoring Design

Date: 2026-06-22

## Context

`TrendResearchAgent` currently computes `trend_score` with a hard source-count rule:

- `7.0` when at least 3 sources are found
- `5.5` otherwise

It also computes `confidence` mostly from source count. This makes the field easy to audit, but it gives the wrong product meaning: many indexed sources can still describe a weak or negative market trend. In that case, the current rule may still produce a high trend score.

The desired behavior is:

- `trend_score` should mean market trend strength.
- `confidence` should mean how reliable the trend judgment is.
- `source_count` should remain the raw evidence quantity used for audit and fallback logic.

## Decision

Use LLM-based content scoring as the primary path, with source-count rule scoring as the fallback.

`TrendResearchAgent` will continue to retrieve and normalize sources from `research_plan.trend_queries`. When `llm_fn` is available, it will pass source snippets and content to the LLM and request structured JSON. The LLM will score the actual market trend based on the indexed content, including positive demand signals, seasonality, growth indicators, weak demand, negative press, and contradictory evidence.

When the LLM is unavailable or returns invalid JSON, the agent will keep the current source-count rule fallback, but explicitly mark the result as rule-scored so consumers do not confuse it with content analysis.

## Output Schema

`trend_result` will include these fields:

```json
{
  "summary": "string",
  "summary_source": "llm | template",
  "trend_score": 0.0,
  "confidence": 0.0,
  "scored_by": "llm | rule",
  "key_findings": ["string"],
  "negative_signals": ["string"],
  "scoring_rationale": "string",
  "evidence": []
}
```

Existing consumers can continue reading:

- `trend_result.summary`
- `trend_result.trend_score`
- `trend_result.evidence`
- `trend_result.confidence`

New fields add auditability without requiring immediate report UI changes.

## Score Semantics

`trend_score` is a 0-10 market trend strength score:

- `8.0-10.0`: strong positive trend, with multiple sources indicating demand growth, visible content/search momentum, or recurring seasonal upside.
- `6.0-7.9`: moderately positive trend, with useful positive signals but incomplete evidence or some uncertainty.
- `4.0-5.9`: neutral or mixed trend, with weak, unclear, or contradictory demand signals.
- `0.0-3.9`: weak or negative trend, with declining demand, strong negative coverage, poor category momentum, or adverse market signals.

The score must not include competition, profit margin, or ease of market entry. Those dimensions remain the responsibility of `OpportunityScoringAgent`.

## Confidence Semantics

`confidence` is a hybrid reliability estimate for the trend judgment.

The source count provides a base level of confidence. The LLM can then adjust based on:

- source relevance to the queried product category and target market
- consistency of signals across sources
- whether sources contain concrete demand or growth evidence
- whether negative or contradictory signals are present
- whether the summary and score are supported by the retrieved evidence

Expected behavior:

- Few sources should cap confidence even when the trend score is high.
- Many sources with contradictory signals should not produce high confidence.
- Many relevant and consistent sources can approach the existing cap of `0.9`.
- Internal agent failure should keep the existing low-confidence fallback, around `0.2`.

## LLM Prompt Contract

The trend scoring prompt should request only JSON, for example:

```json
{
  "summary": "2-4 Chinese sentences grounded in the sources",
  "trend_score": 0-10,
  "confidence": 0-0.9,
  "key_findings": ["2-5 concise Chinese findings"],
  "negative_signals": ["0-5 concise Chinese negative or weak signals"],
  "scoring_rationale": "one concise Chinese explanation"
}
```

The prompt should explicitly say:

- Base the answer only on supplied sources.
- Do not invent exact numbers not present in the sources.
- Trend score evaluates market trend strength only.
- Lower the trend score when sources mainly indicate weak demand, negative news, or declining momentum.
- Lower confidence when evidence is sparse, noisy, irrelevant, or contradictory.

## Fallback Behavior

If `llm_fn` is missing, LLM budget is unavailable, or JSON parsing fails:

- Keep the source-count fallback for compatibility.
- Set `scored_by` to `"rule"`.
- Set `summary_source` to `"template"` unless a usable LLM summary exists.
- Set `scoring_rationale` to explain that the score is estimated from source count only.
- Preserve the current `source_count < 2` partial status behavior.

The fallback should remain conservative in wording because it does not inspect content sentiment or direction.

## Downstream Impact

`OpportunityScoringAgent` can continue reading `trend_result.trend_score`; the value will become a better input because it reflects content-level trend strength when LLM scoring succeeds.

`audit_log` should continue recording:

- `source_count`: number of evidence items
- `confidence`: trend judgment reliability
- `warning`: data or LLM fallback warning when relevant

Reports and frontend pages do not need to change immediately. A later UI improvement can display `scored_by`, `negative_signals`, and `scoring_rationale`.

## Test Cases

Add focused tests around `TrendResearchAgent`:

1. LLM success with positive sources returns an LLM-scored high `trend_score`, `scored_by="llm"`, and populated rationale.
2. LLM success with negative or weak sources returns a low or mixed `trend_score` even when `source_count >= 3`.
3. LLM returns invalid JSON; the agent falls back to the rule score and marks `scored_by="rule"`.
4. No sources or search failure keeps low-confidence fallback behavior and records a warning.
5. Existing downstream scoring still reads `trend_result.trend_score` without schema breakage.

## Non-Goals

- Do not change competition, margin, risk, or final opportunity scoring weights in this design.
- Do not add keyword sentiment scoring as a fallback in this iteration.
- Do not require frontend or report rendering changes for the first implementation.
