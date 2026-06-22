# Ecommerce Research Node Content Scoring Design

Date: 2026-06-22

## Context

`TrendResearchAgent` currently computes `trend_score` with a hard source-count rule:

- `7.0` when at least 3 sources are found
- `5.5` otherwise

It also computes `confidence` mostly from source count. This makes the field easy to audit, but it gives the wrong product meaning: many indexed sources can still describe a weak or negative market trend. In that case, the current rule may still produce a high trend score.

The other two research nodes have similar source-count shortcuts:

- `CompetitorAnalysisAgent` computes `competition_score` from source count, even though downstream scoring interprets a higher score as easier market entry.
- `ReviewInsightAgent` computes `pain_point_score` from the number of extracted pain points, even though many pain points can mean either strong unmet need or a risky, low-quality category.

The desired behavior is:

- `trend_score` should mean market trend strength.
- `competition_score` should mean ease of competitive entry, not raw competitor evidence volume.
- `pain_point_score` should mean actionable unmet-need opportunity, not raw complaint count.
- `confidence` should mean how reliable each node judgment is.
- `source_count` should remain the raw evidence quantity used for audit and fallback logic.

## Decision

Use LLM-based content scoring as the primary path for the three research nodes, with the existing rule scores as fallbacks.

`TrendResearchAgent` will continue to retrieve and normalize sources from `research_plan.trend_queries`. When `llm_fn` is available, it will pass source snippets and content to the LLM and request structured JSON. The LLM will score the actual market trend based on the indexed content, including positive demand signals, seasonality, growth indicators, weak demand, negative press, and contradictory evidence.

`CompetitorAnalysisAgent` will continue to retrieve sources from `research_plan.competitor_queries`. When `llm_fn` is available, it will score competitive entry ease from content-level signals, including number and strength of competitors, price band crowding, differentiation opportunities, commodity risk, and dominance of strong brands or platforms.

`ReviewInsightAgent` will continue to prefer Apify real reviews and fall back to web search reviews. When `llm_fn` is available, it will score whether extracted pain points represent actionable opportunity. It should distinguish solvable unmet needs from structural category risks, poor product-market fit, or generic complaints.

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

`competitor_result` will include these added fields:

```json
{
  "competition_score": 0.0,
  "confidence": 0.0,
  "scored_by": "llm | rule",
  "competitive_signals": ["string"],
  "entry_barriers": ["string"],
  "scoring_rationale": "string"
}
```

`review_result` will include these added fields:

```json
{
  "pain_point_score": 0.0,
  "confidence": 0.0,
  "scored_by": "llm | rule",
  "actionable_pain_points": ["string"],
  "structural_risks": ["string"],
  "scoring_rationale": "string"
}
```

Existing result fields such as `summary`, `competitors`, `price_range`, `pain_points`, `review_source`, and `evidence` remain available.

## Score Semantics

### Trend Score

`trend_score` is a 0-10 market trend strength score:

- `8.0-10.0`: strong positive trend, with multiple sources indicating demand growth, visible content/search momentum, or recurring seasonal upside.
- `6.0-7.9`: moderately positive trend, with useful positive signals but incomplete evidence or some uncertainty.
- `4.0-5.9`: neutral or mixed trend, with weak, unclear, or contradictory demand signals.
- `0.0-3.9`: weak or negative trend, with declining demand, strong negative coverage, poor category momentum, or adverse market signals.

The score must not include competition, profit margin, or ease of market entry. Those dimensions remain the responsibility of `OpportunityScoringAgent`.

### Competition Score

`competition_score` is a 0-10 competitive entry ease score. Higher means easier to enter, not more competition.

- `8.0-10.0`: fragmented market, weak incumbents, clear differentiation space, or many comparable products with obvious gaps.
- `6.0-7.9`: moderate entry room, with some established competitors but visible positioning or feature gaps.
- `4.0-5.9`: crowded or unclear market, with limited differentiation evidence.
- `0.0-3.9`: hard entry, with dominant brands, severe price compression, commodity competition, or little room for differentiation.

This direction matches `OpportunityScoringAgent`, where a higher competition dimension should improve the final opportunity score.

### Pain Point Score

`pain_point_score` is a 0-10 actionable unmet-need opportunity score.

- `8.0-10.0`: frequent, concrete, and solvable pain points that can map to product, listing, packaging, support, or positioning improvements.
- `6.0-7.9`: useful pain points exist, but frequency, solvability, or buyer importance is less certain.
- `4.0-5.9`: complaints are generic, sparse, or only weakly connected to a new product opportunity.
- `0.0-3.9`: pain points mainly indicate structural category risk, safety/compliance issues, low willingness to pay, or problems that are hard to solve.

The score should not increase only because there are many complaints.

## Confidence Semantics

`confidence` is a hybrid reliability estimate for each node's judgment.

The source count provides a base level of confidence. The LLM can then adjust based on:

- source relevance to the queried product category and target market
- consistency of signals across sources
- whether sources contain concrete evidence for the node's scoring dimension
- whether negative or contradictory signals are present
- whether the summary and score are supported by the retrieved evidence

Expected behavior:

- Few sources should cap confidence even when the score is high.
- Many sources with contradictory signals should not produce high confidence.
- Many relevant and consistent sources can approach the existing cap of `0.9`.
- Internal agent failure should keep the existing low-confidence fallback, around `0.2`.

## LLM Prompt Contract

Each scoring prompt should request only JSON.

The trend prompt should return:

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

The competitor prompt should return:

```json
{
  "summary": "2-4 Chinese sentences grounded in the sources",
  "competition_score": 0-10,
  "confidence": 0-0.9,
  "competitors": [{"name": "string", "positioning": "string"}],
  "competitive_signals": ["2-5 concise Chinese signals"],
  "entry_barriers": ["0-5 concise Chinese barriers"],
  "differentiation_opportunities": ["2-5 concise Chinese opportunities"],
  "scoring_rationale": "one concise Chinese explanation"
}
```

The competitor prompt should explicitly say:

- A higher `competition_score` means easier entry.
- Do not reward source count by itself.
- Lower the score when sources show dominant brands, price wars, commodity products, or little differentiation space.
- Raise the score when sources show fragmented competitors, unresolved buyer needs, or clear positioning gaps.

The review prompt should return:

```json
{
  "summary": "2-4 Chinese sentences grounded in the reviews",
  "pain_points": ["3-6 Chinese pain points"],
  "pain_point_score": 0-10,
  "confidence": 0-0.9,
  "actionable_pain_points": ["2-5 concise Chinese opportunities"],
  "structural_risks": ["0-5 concise Chinese risks"],
  "scoring_rationale": "one concise Chinese explanation"
}
```

The review prompt should explicitly say:

- A higher `pain_point_score` means more actionable unmet-need opportunity.
- Do not reward complaint count by itself.
- Lower the score when complaints are mainly safety, compliance, durability, or category-level risks that are hard to solve.
- Raise the score when pain points are frequent, specific, buyer-relevant, and can be addressed through product or listing improvements.

## Fallback Behavior

If `llm_fn` is missing, LLM budget is unavailable, or JSON parsing fails:

- Keep the existing rule fallback for compatibility.
- Set `scored_by` to `"rule"`.
- Set `summary_source` to `"template"` unless a usable LLM summary exists.
- Set `scoring_rationale` to explain that the score is estimated from a simple rule only.
- Preserve the current `source_count < 2` partial status behavior.

The fallback should remain conservative in wording because it does not inspect the full content semantics.

Fallback meanings:

- Trend: current source-count fallback estimates trend signal coverage.
- Competitor: current source-count fallback estimates competitor evidence coverage, not true entry ease.
- Review: current pain-point-count fallback estimates complaint coverage, not true actionable opportunity.

## Downstream Impact

`OpportunityScoringAgent` can continue reading `trend_result.trend_score`, `competitor_result.competition_score`, and `review_result.pain_point_score`. These values will become better inputs because they reflect content-level judgments when LLM scoring succeeds.

`audit_log` should continue recording:

- `source_count`: number of evidence items
- `confidence`: trend judgment reliability
- `warning`: data or LLM fallback warning when relevant

Reports and frontend pages do not need to change immediately. A later UI improvement can display `scored_by`, `negative_signals`, and `scoring_rationale`.

## Test Cases

Add focused tests around the three research nodes:

1. LLM success with positive sources returns an LLM-scored high `trend_score`, `scored_by="llm"`, and populated rationale.
2. LLM success with negative or weak sources returns a low or mixed `trend_score` even when `source_count >= 3`.
3. LLM success with strong incumbents or price-war competitor sources returns a low `competition_score` even when `source_count >= 3`.
4. LLM success with fragmented competitors and clear differentiation gaps returns a high `competition_score`.
5. LLM success with many structural complaints returns a low or mixed `pain_point_score`, not an automatic high score.
6. LLM success with solvable, frequent pain points returns a high `pain_point_score`.
7. LLM returns invalid JSON; the agent falls back to the rule score and marks `scored_by="rule"`.
8. No sources or search failure keeps low-confidence fallback behavior and records a warning.
9. Existing downstream scoring still reads the three score fields without schema breakage.

## Non-Goals

- Do not change competition, margin, risk, or final opportunity scoring weights in this design.
- Do not add keyword sentiment scoring as a fallback in this iteration.
- Do not require frontend or report rendering changes for the first implementation.
- Do not replace Apify review scraping or fallback web review extraction in this iteration.
