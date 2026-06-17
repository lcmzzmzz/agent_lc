"""
ReviewInsightAgent：用户评论痛点洞察（含 LLM 中文归纳）。

【正经注释】
异步节点。消费 research_plan.review_queries，检索后用 review_extractor 抽取抱怨句子；
若注入 llm_fn 可用，再用 LLM 把（多为英文的）原始反馈归纳为中文痛点列表，
LLM 不可用则保留原文并标注 pain_points_language=en。失败走 fallback，不中断流程。
pain_points_language 字段记录最终痛点语言（zh/en/none），便于审计与展示。

【大白话注释】
搜用户评论，把抱怨句挑出来。如果配了大模型，就把这些（通常是英文的）反馈
归纳成几条中文痛点；大模型用不了就保留英文原文，并标清楚语言。
"""

from __future__ import annotations

import logging
import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.llm_helper import LlmFn, llm_json
from multi_agents.ecommerce.prompts import REVIEW_INSIGHT_SYSTEM_PROMPT
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources
from multi_agents.ecommerce.tools.review_extractor import extract_review_insights

logger = logging.getLogger(__name__)

_RESULTS_PER_QUERY = 3


async def _summarize_pain_points_zh(
    llm_fn: LlmFn | None, pain_points: list[str]
) -> tuple[list[str] | None, bool]:
    """用 LLM 把原始（多为英文）反馈归纳为中文痛点。返回 (zh_list | None, used_llm)。"""
    if not llm_fn or not pain_points:
        return None, False
    user = (
        "以下是从公开资料抽取的用户反馈（可能为英文）：\n"
        + "\n".join(f"- {p}" for p in pain_points[:10])
        + "\n请把它们归纳成 3-6 条中文用户痛点，每条一句话，客观描述问题。"
        '只返回 JSON：{"pain_points":["中文痛点1","中文痛点2"]}'
    )
    data, used = await llm_json(llm_fn, REVIEW_INSIGHT_SYSTEM_PROMPT, user)
    if used and isinstance(data.get("pain_points"), list) and data["pain_points"]:
        zh = [str(p) for p in data["pain_points"] if p][:6]
        if zh:
            return zh, True
    return None, False


async def run_review_insight(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
    llm_fn: LlmFn | None = None,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    queries = state["research_plan"].get("review_queries", [])
    logger.info(f"[ReviewInsight] 开始 query='{state['query']}' queries={len(queries)}")

    try:
        sources = await search_sources(
            queries=queries,
            search_fn=search_fn,
            max_results_per_query=_RESULTS_PER_QUERY,
        )
        limited_sources = sources[: config["max_sources_per_agent"]]
        raw_pain_points = extract_review_insights(limited_sources)
        source_count = len(limited_sources)
        logger.info(
            f"[ReviewInsight] 检索完成 sources={source_count} 原始痛点={len(raw_pain_points)}"
        )

        # LLM 中文归纳（可用则覆盖；不可用保留英文原文）
        zh_pain_points, used_llm = await _summarize_pain_points_zh(llm_fn, raw_pain_points)
        final_pain_points = zh_pain_points or raw_pain_points
        language = "zh" if used_llm else ("en" if raw_pain_points else "none")
        if raw_pain_points and not used_llm and llm_fn:
            logger.warning("[ReviewInsight] LLM 中文归纳失败，保留英文原文")

        state["review_result"] = {
            "summary": "公开评论和评测内容可用于提取用户痛点，但仍需真实平台评论进一步验证。",
            "pain_points": final_pain_points,
            "purchase_motivations": ["便携性", "使用便利性", "适合特定生活方式场景"],
            "negative_review_patterns": final_pain_points[:5],
            "opportunity_insights": [
                "将高频抱怨点转化为产品改进点。",
                "在 Listing 中明确使用场景和限制，降低预期偏差。",
            ],
            "pain_point_score": 8.0 if len(final_pain_points) >= 3 else 5.5,
            "evidence": limited_sources,
            "confidence": round(min(0.9, 0.3 + len(final_pain_points) * 0.08), 2),
            "pain_points_language": language,
        }
        status = "success" if final_pain_points else "partial"
        warning = None if final_pain_points else "review pain point data limited"
        logger.info(
            f"[ReviewInsight] 完成 status={status} 痛点语言={language} 痛点数={len(final_pain_points)}"
        )
    except Exception as exc:
        logger.error(f"[ReviewInsight] 失败: {exc}", exc_info=True)
        state["review_result"] = {
            "summary": "评论数据不足，无法形成高置信度痛点分析。",
            "pain_points": [],
            "purchase_motivations": [],
            "negative_review_patterns": [],
            "opportunity_insights": [],
            "pain_point_score": 4.0,
            "evidence": [],
            "confidence": 0.2,
            "pain_points_language": "none",
            "error": str(exc),
        }
        state["errors"].append({"agent": "ReviewInsightAgent", "error": str(exc)})
        status = "partial"
        warning = "review insight failed"

    state["audit_log"].append(
        {
            "agent": "ReviewInsightAgent",
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": len(state["review_result"].get("evidence", [])),
            "confidence": state["review_result"].get("confidence", 0.0),
            "warning": warning,
        }
    )
    return state
