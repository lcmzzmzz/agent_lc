"""
ReviewInsightAgent：用户评论痛点洞察。

【正经注释】
异步节点。消费 research_plan.review_queries，检索后用 review_extractor
从结果中抽取抱怨/痛点句子，产出 pain_points、购买动机、可转化卖点机会与痛点评分。
这是该垂直工作流的亮点模块：把公开评论/评测文本结构化为选品决策信号。
失败走 fallback，不中断流程。

【大白话注释】
搜用户评论、差评相关内容，把"抱怨句"挑出来当成痛点素材，
再据此推测能怎么改进产品、怎么做卖点。
"""

from __future__ import annotations

import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources
from multi_agents.ecommerce.tools.review_extractor import extract_review_insights

_RESULTS_PER_QUERY = 3


async def run_review_insight(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    queries = state["research_plan"].get("review_queries", [])

    try:
        sources = await search_sources(
            queries=queries,
            search_fn=search_fn,
            max_results_per_query=_RESULTS_PER_QUERY,
        )
        limited_sources = sources[: config["max_sources_per_agent"]]
        pain_points = extract_review_insights(limited_sources)

        state["review_result"] = {
            "summary": "公开评论和评测内容可用于提取用户痛点，但仍需真实平台评论进一步验证。",
            "pain_points": pain_points,
            "purchase_motivations": ["便携性", "使用便利性", "适合特定生活方式场景"],
            "negative_review_patterns": pain_points[:5],
            "opportunity_insights": [
                "将高频抱怨点转化为产品改进点。",
                "在 Listing 中明确使用场景和限制，降低预期偏差。",
            ],
            "pain_point_score": 8.0 if len(pain_points) >= 3 else 5.5,
            "evidence": limited_sources,
            "confidence": round(min(0.9, 0.3 + len(pain_points) * 0.08), 2),
        }
        status = "success" if pain_points else "partial"
        warning = None if pain_points else "review pain point data limited"
    except Exception as exc:
        state["review_result"] = {
            "summary": "评论数据不足，无法形成高置信度痛点分析。",
            "pain_points": [],
            "purchase_motivations": [],
            "negative_review_patterns": [],
            "opportunity_insights": [],
            "pain_point_score": 4.0,
            "evidence": [],
            "confidence": 0.2,
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
