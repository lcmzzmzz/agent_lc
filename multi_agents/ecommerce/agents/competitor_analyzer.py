"""
CompetitorAnalysisAgent：竞品格局分析。

【正经注释】
异步节点。消费 research_plan.competitor_queries，检索后从结果文本中用正则
提取价格区间（$N 形式），产出竞争强度评分、差异化机会与数据源。
失败走 fallback，不中断流程。

【大白话注释】
搜竞品相关资料，从里面抠出价格（比如 $30），给竞争打分，
再说说能从哪几个角度做差异化。搜不到就降级。
"""

from __future__ import annotations

import re
import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources

_RESULTS_PER_QUERY = 3
_PRICE_RE = re.compile(r"\$(\d+)")


def infer_price_range(text: str) -> str:
    """从文本中提取 $N 价格，返回 "$min-$max" 区间；无则给默认区间。"""
    prices = [int(match) for match in _PRICE_RE.findall(text)]
    if prices:
        return f"${min(prices)}-${max(prices)}"
    return "$20-$60"


async def run_competitor_analysis(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    queries = state["research_plan"].get("competitor_queries", [])

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

        state["competitor_result"] = {
            "summary": "该品类已有较多公开竞品和评测信息，适合进一步做差异化分析。",
            "competitors": [
                {"name": "Top marketplace products", "positioning": "mainstream competitor group"}
            ],
            "price_range": infer_price_range(combined_text),
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
    except Exception as exc:
        state["competitor_result"] = {
            "summary": "竞品数据获取失败，无法形成高置信度竞品判断。",
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
