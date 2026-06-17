"""
TrendResearchAgent：市场趋势研究。

【正经注释】
异步节点。消费 research_plan.trend_queries，调用注入的 search_fn 检索，
标准化后截断到该深度档位的最大数据源数，产出 trend_score/key_findings/evidence/confidence。
检索失败或数据不足时走 fallback：低置信度、低分，写入 audit_log，不抛异常中断流程。

【大白话注释】
按规划阶段列的"趋势关键词"去搜，搜到的资料整理好，给个趋势打分。
搜不到也没关系，给个低分继续往下走，不让整条流程断掉。
"""

from __future__ import annotations

import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources

# 每条查询请求的最大结果数（整体还会按档位 max_sources_per_agent 截断）
_RESULTS_PER_QUERY = 3


async def run_trend_research(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    queries = state["research_plan"].get("trend_queries", [])

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

        state["trend_result"] = {
            "summary": f"{state['query']} 在 {state['target_market']} 市场存在可调研需求信号。",
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
    except Exception as exc:  # 任何异常都不中断主流程
        state["trend_result"] = {
            "summary": "趋势数据获取失败，无法形成高置信度趋势判断。",
            "trend_score": 4.0,
            "key_findings": [],
            "evidence": [],
            "confidence": 0.2,
            "error": str(exc),
        }
        state["errors"].append({"agent": "TrendResearchAgent", "error": str(exc)})
        status = "partial"
        warning = "trend research failed"

    state["audit_log"].append(
        {
            "agent": "TrendResearchAgent",
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": len(state["trend_result"].get("evidence", [])),
            "confidence": state["trend_result"].get("confidence", 0.0),
            "warning": warning,
        }
    )
    return state
