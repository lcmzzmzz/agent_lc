"""
ProductResearchPlannerAgent：选品调研规划。

【正经注释】
同步节点。根据品类关键词、目标市场与调研深度，生成趋势/竞品/评论/风险四类查询，
并固定评分维度与风险关注点，写入 research_plan。
不依赖外部检索与 LLM，输出确定性强、可被后续并发研究节点直接消费。

【大白话注释】
这一步不搜东西，只做"分工"：把"研究 portable blender"拆成趋势、竞品、评论几组
搜索关键词，再规定打分要打哪几项、风险看哪几点。后面的人照着这个清单干活。
"""

from __future__ import annotations

import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import build_ecommerce_queries
from multi_agents.ecommerce.agents.audit import finalize_audit


def run_planner(state: EcommerceResearchState) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    max_queries = config["max_queries_per_agent"]

    query = state["query"]
    market = state["target_market"]

    state["research_plan"] = {
        "trend_queries": build_ecommerce_queries(
            query=query, target_market=market, intent="trend", max_queries=max_queries
        ),
        "competitor_queries": build_ecommerce_queries(
            query=query, target_market=market, intent="competitor", max_queries=max_queries
        ),
        "review_queries": build_ecommerce_queries(
            query=query, target_market=market, intent="review", max_queries=max_queries
        ),
        "risk_focus": [
            "platform policy risk",
            "shipping and after-sales risk",
            "product quality complaints",
            "data source limitation",
        ],
        "scoring_dimensions": [
            "trend_score",
            "competition_score",
            "pain_point_score",
            "margin_score",
            "risk_score",
            "evidence_score",
        ],
    }

    finalize_audit(
        state,
        "ProductResearchPlannerAgent",
        status="success",
        source_count=0,
        confidence=1.0,
        warning=None,
        started=started,
    )
    return state
