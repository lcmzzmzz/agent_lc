"""CompetitorAnalysisAgent: research competitor content and score entry ease."""

from __future__ import annotations

import logging
import re
import time

from multi_agents.ecommerce.agents.audit import finalize_audit
from multi_agents.ecommerce.agents.content_scoring import (
    coerce_competitors,
    coerce_confidence,
    coerce_score,
    coerce_string_list,
    format_sources_for_prompt,
    rule_rationale,
    source_count_confidence,
)
from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.llm_helper import LlmFn, llm_json
from multi_agents.ecommerce.prompts import COMPETITOR_ANALYZER_SYSTEM_PROMPT
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources

logger = logging.getLogger(__name__)

_RESULTS_PER_QUERY = 3
_PRICE_RE = re.compile(r"\$(\d+)")
_TEMPLATE_SUMMARY = (
    "该品类已有较多公开竞品和评测信息，适合进一步做差异化分析。"
)


def infer_price_range(text: str) -> str:
    """Extract a simple USD price range from source text."""
    prices = [int(match) for match in _PRICE_RE.findall(text)]
    if prices:
        return f"${min(prices)}-${max(prices)}"
    return "$20-$60"


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


async def run_competitor_analysis(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
    llm_fn: LlmFn | None = None,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    queries = state["research_plan"].get("competitor_queries", [])
    logger.info(f"[Competitor] start query='{state['query']}' queries={len(queries)}")

    try:
        sources = await search_sources(
            queries=queries,
            search_fn=search_fn,
            max_results_per_query=_RESULTS_PER_QUERY,
        )
        limited_sources = sources[: config["max_sources_per_agent"]]
        combined_text = " ".join(
            f"{source.get('snippet', '')} {source.get('content', '')}"
            for source in limited_sources
        )
        source_count = len(limited_sources)
        price_range = infer_price_range(combined_text)

        competitors: list[dict[str, str]] = []
        seen_names: set[str] = set()
        for source in limited_sources:
            name = (source.get("title") or "").strip()
            short = name.split("|")[0].split(":")[0].strip()[:60]
            key = short.lower()
            if short and key not in seen_names:
                seen_names.add(key)
                competitors.append(
                    {"name": short, "positioning": "公开搜索结果中的代表性产品"}
                )
            if len(competitors) >= 3:
                break
        if not competitors:
            competitors = [
                {
                    "name": "公开搜索结果中的代表性竞品",
                    "positioning": "需补充具体品牌数据",
                }
            ]

        differentiation_opportunities: list[str] = []
        if price_range and price_range != "unknown":
            differentiation_opportunities.append(f"围绕 {price_range} 价格带做差异化定位。")
        if source_count >= 3:
            differentiation_opportunities.append("结合公开评测中的高频关注点优化产品功能。")
        differentiation_opportunities.append(
            "通过清晰场景定位与目标人群差异化，避免同质化竞争。"
        )

        rule_confidence = source_count_confidence(source_count)
        rule_competition_score = 6.0 if source_count >= 3 else 5.0
        llm_data, used_llm = await _llm_competitor_score(
            llm_fn, state["query"], state["target_market"], limited_sources, price_range
        )
        if llm_fn and not used_llm:
            logger.warning("[Competitor] LLM scoring failed; falling back to rule score")

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

        state["competitor_result"] = {
            "summary": summary,
            "summary_source": "llm" if used_llm else "template",
            "competitors": competitors,
            "price_range": price_range,
            "competition_score": competition_score,
            "competitive_signals": competitive_signals,
            "entry_barriers": entry_barriers,
            "differentiation_opportunities": differentiation_opportunities,
            "scoring_rationale": scoring_rationale,
            "scored_by": "llm" if used_llm else "rule",
            "evidence": limited_sources,
            "confidence": confidence,
        }
        status = "success" if source_count >= 2 else "partial"
        warning = None if source_count >= 2 else "competitor source data limited"
        logger.info(
            "[Competitor] done status=%s summary_source=%s price=%s",
            status,
            state["competitor_result"]["summary_source"],
            price_range,
        )
    except Exception as exc:
        logger.error(f"[Competitor] failed: {exc}", exc_info=True)
        state["competitor_result"] = {
            "summary": _TEMPLATE_SUMMARY,
            "summary_source": "template",
            "competitors": [],
            "price_range": "unknown",
            "competition_score": 4.0,
            "competitive_signals": [],
            "entry_barriers": [],
            "differentiation_opportunities": [],
            "scoring_rationale": "Competitor analysis failed before content scoring.",
            "scored_by": "rule",
            "evidence": [],
            "confidence": 0.2,
            "error": str(exc),
        }
        state["errors"].append({"agent": "CompetitorAnalysisAgent", "error": str(exc)})
        status = "partial"
        warning = "competitor analysis failed"

    finalize_audit(
        state,
        "CompetitorAnalysisAgent",
        status=status,
        source_count=len(state["competitor_result"].get("evidence", [])),
        confidence=state["competitor_result"].get("confidence", 0.0),
        warning=warning,
        started=started,
    )
    return state
