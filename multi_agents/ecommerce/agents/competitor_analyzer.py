"""
CompetitorAnalysisAgent：竞品格局分析（summary 已 LLM 化）。

【正经注释】
异步节点。消费 research_plan.competitor_queries，检索后用正则抽价格区间，
并把检索资料喂给 llm_fn 让其生成中文竞品 summary；LLM 不可用回退模板。
competition_score 按数据源数量算，evidence 保留来源。失败走 fallback，不中断流程。

【大白话注释】
搜竞品资料，从里面抠价格（$N），再让大模型写一段中文竞品总结；
大模型用不了就用固定模板。价格还是正则抽，竞争分按"搜到几条"算。
"""

from __future__ import annotations

import logging
import re
import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.llm_helper import LlmFn, llm_text
from multi_agents.ecommerce.prompts import COMPETITOR_ANALYZER_SYSTEM_PROMPT
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources

logger = logging.getLogger(__name__)

_RESULTS_PER_QUERY = 3
_PRICE_RE = re.compile(r"\$(\d+)")
_TEMPLATE_SUMMARY = "该品类已有较多公开竞品和评测信息，适合进一步做差异化分析。"


def infer_price_range(text: str) -> str:
    """从文本中提取 $N 价格，返回 "$min-$max" 区间；无则给默认区间。"""
    prices = [int(match) for match in _PRICE_RE.findall(text)]
    if prices:
        return f"${min(prices)}-${max(prices)}"
    return "$20-$60"


async def _llm_competitor_summary(
    llm_fn: LlmFn | None, query: str, market: str, sources: list, price_range: str
) -> str | None:
    """用 LLM 基于检索资料生成中文竞品总结；不可用返回 None。"""
    if not llm_fn or not sources:
        return None
    text = "\n".join(
        f"- {s.get('snippet', '')} {s.get('content', '')}" for s in sources[:8]
    )[:3000]
    user = (
        f"品类：{query}（市场：{market}）\n初步价格区间：{price_range}\n"
        f"以下是与该品类竞品相关的公开资料：\n{text}\n"
        "请用 2-4 句中文总结该品类的竞品格局（主要玩家 / 价格带 / 竞争强度 / 差异化机会），"
        "客观且基于资料，不要编造品牌名和数字。直接输出总结文字，不要 JSON。"
    )
    summary, used = await llm_text(llm_fn, COMPETITOR_ANALYZER_SYSTEM_PROMPT, user)
    return summary if used else None


async def run_competitor_analysis(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
    llm_fn: LlmFn | None = None,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    queries = state["research_plan"].get("competitor_queries", [])
    logger.info(f"[Competitor] 开始 query='{state['query']}' queries={len(queries)}")

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

        # summary LLM 化（基于真实资料 + 价格），失败回退模板
        llm_summary = await _llm_competitor_summary(
            llm_fn, state["query"], state["target_market"], limited_sources, price_range
        )
        summary = llm_summary or _TEMPLATE_SUMMARY
        if llm_fn and not llm_summary:
            logger.warning("[Competitor] LLM summary 失败，回退模板")

        state["competitor_result"] = {
            "summary": summary,
            "summary_source": "llm" if llm_summary else "template",
            "competitors": [
                {"name": "Top marketplace products", "positioning": "mainstream competitor group"}
            ],
            "price_range": price_range,
            "competition_score": 6.0 if source_count >= 3 else 5.0,
            "differentiation_opportunities": [
                "围绕差评痛点优化产品功能。",
                "通过清晰场景定位避免同质化竞争。",
            ],
            "evidence": limited_sources,
            "confidence": round(min(0.9, 0.35 + source_count * 0.1), 2),
        }
        status = "success" if source_count >= 2 else "partial"
        warning = None if source_count >= 2 else "competitor source data limited"
        logger.info(
            f"[Competitor] 完成 status={status} summary_source={state['competitor_result']['summary_source']} price={price_range}"
        )
    except Exception as exc:
        logger.error(f"[Competitor] 失败: {exc}", exc_info=True)
        state["competitor_result"] = {
            "summary": _TEMPLATE_SUMMARY,
            "summary_source": "template",
            "competitors": [],
            "price_range": "unknown",
            "competition_score": 4.0,
            "differentiation_opportunities": [],
            "evidence": [],
            "confidence": 0.2,
            "error": str(exc),
        }
        state["errors"].append({"agent": "CompetitorAnalysisAgent", "error": str(exc)})
        status = "partial"
        warning = "competitor analysis failed"

    state["audit_log"].append(
        {
            "agent": "CompetitorAnalysisAgent",
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": len(state["competitor_result"].get("evidence", [])),
            "confidence": state["competitor_result"].get("confidence", 0.0),
            "warning": warning,
        }
    )
    return state
