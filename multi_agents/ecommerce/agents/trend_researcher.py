"""
TrendResearchAgent：市场趋势研究（summary 已 LLM 化）。

【正经注释】
异步节点。消费 research_plan.trend_queries，检索后把标准化数据源的 snippet/content
拼接喂给 llm_fn，让 LLM 基于真实资料生成中文趋势 summary；LLM 不可用则回退模板。
trend_score 仍按数据源数量客观计算，evidence 保留来源。失败走 fallback，不中断流程。

【大白话注释】
搜趋势资料，把搜到的内容喂给大模型让它写一段中文趋势总结；
大模型用不了就用原来的固定模板。分数还是按"搜到几条"算。
"""

from __future__ import annotations

import logging
import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.llm_helper import LlmFn, llm_text
from multi_agents.ecommerce.prompts import TREND_RESEARCHER_SYSTEM_PROMPT
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources
from multi_agents.ecommerce.agents.audit import finalize_audit

logger = logging.getLogger(__name__)

_RESULTS_PER_QUERY = 3
_TEMPLATE_SUMMARY = "{query} 在 {market} 市场存在可调研需求信号。"


async def _llm_trend_summary(
    llm_fn: LlmFn | None, query: str, market: str, sources: list
) -> str | None:
    """用 LLM 基于检索资料生成中文趋势总结；不可用返回 None。"""
    if not llm_fn or not sources:
        return None
    text = "\n".join(
        f"- {s.get('snippet', '')} {s.get('content', '')}" for s in sources[:8]
    )[:3000]
    user = (
        f"品类：{query}（市场：{market}）\n"
        f"以下是与该品类市场趋势相关的公开资料：\n{text}\n"
        "请用 2-4 句中文总结该品类的市场趋势（需求热度 / 季节性 / 增长信号），"
        "客观且基于资料，不要编造具体数字。直接输出总结文字，不要 JSON。"
    )
    summary, used = await llm_text(llm_fn, TREND_RESEARCHER_SYSTEM_PROMPT, user)
    return summary if used else None


async def run_trend_research(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
    llm_fn: LlmFn | None = None,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    queries = state["research_plan"].get("trend_queries", [])
    logger.info(f"[Trend] 开始 query='{state['query']}' queries={len(queries)}")

    try:
        sources = await search_sources(
            queries=queries,
            search_fn=search_fn,
            max_results_per_query=_RESULTS_PER_QUERY,
        )
        limited_sources = sources[: config["max_sources_per_agent"]]
        source_count = len(limited_sources)
        confidence = round(min(0.9, 0.35 + source_count * 0.1), 2)
        trend_score = 7.0 if source_count >= 3 else 5.5

        # summary LLM 化（基于真实资料），失败回退模板
        llm_summary = await _llm_trend_summary(
            llm_fn, state["query"], state["target_market"], limited_sources
        )
        summary = llm_summary or _TEMPLATE_SUMMARY.format(
            query=state["query"], market=state["target_market"]
        )
        if llm_fn and not llm_summary:
            logger.warning("[Trend] LLM summary 失败，回退模板")

        state["trend_result"] = {
            "summary": summary,
            "summary_source": "llm" if llm_summary else "template",
            "trend_score": trend_score,
            "key_findings": [
                "公开资料显示该品类存在搜索和评测内容。",
                "需要结合平台真实销量和供应链成本进一步验证。",
            ],
            "evidence": limited_sources,
            "confidence": confidence,
        }
        status = "success" if source_count >= 2 else "partial"
        warning = None if source_count >= 2 else "trend source data limited"
        logger.info(
            f"[Trend] 完成 status={status} summary_source={state['trend_result']['summary_source']}"
        )
    except Exception as exc:
        logger.error(f"[Trend] 失败: {exc}", exc_info=True)
        state["trend_result"] = {
            "summary": _TEMPLATE_SUMMARY.format(
                query=state["query"], market=state["target_market"]
            ),
            "summary_source": "template",
            "trend_score": 4.0,
            "key_findings": [],
            "evidence": [],
            "confidence": 0.2,
            "error": str(exc),
        }
        state["errors"].append({"agent": "TrendResearchAgent", "error": str(exc)})
        status = "partial"
        warning = "trend research failed"

    finalize_audit(
        state,
        "TrendResearchAgent",
        status=status,
        source_count=len(state["trend_result"].get("evidence", [])),
        confidence=state["trend_result"].get("confidence", 0.0),
        warning=warning,
        started=started,
    )
    return state
