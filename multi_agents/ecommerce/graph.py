"""
EcomResearcher 工作流编排。

【正经注释】
run_ecommerce_graph 把 7 个 Agent 串成一条流水线：
planner(同步) → [trend, competitor, review] 并发 → opportunity_scoring →
report_writer → quality_reviewer。
三个研究节点并发执行，各自持有独立子状态（独立 audit_log/errors），
避免共享可变集合在协程间交错；并发结束后由本函数统一合并结果与日志。

【大白话注释】
这一步是把前面写好的 7 个角色按顺序排好、连起来：
先规划，再让趋势/竞品/评论三个角色同时干活，最后评分、写报告、做质量检查。
三个角色同时干的时候，各自记自己的日志，互不打架，最后再汇总。
"""

from __future__ import annotations

import asyncio

from multi_agents.ecommerce.agents.competitor_analyzer import run_competitor_analysis
from multi_agents.ecommerce.agents.opportunity_scorer import run_opportunity_scoring
from multi_agents.ecommerce.agents.planner import run_planner
from multi_agents.ecommerce.agents.quality_reviewer import run_quality_review
from multi_agents.ecommerce.agents.report_writer import run_report_writer
from multi_agents.ecommerce.agents.review_insight import run_review_insight
from multi_agents.ecommerce.agents.trend_researcher import run_trend_research
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn


def _make_child_state(state: EcommerceResearchState) -> EcommerceResearchState:
    """为并发研究节点构造独立子状态：共享只读字段，独立 audit_log/errors。"""
    return {
        "query": state["query"],
        "target_market": state["target_market"],
        "platforms": state["platforms"],
        "depth": state["depth"],
        "research_plan": state["research_plan"],
        "audit_log": [],
        "errors": [],
    }


async def run_ecommerce_graph(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
) -> EcommerceResearchState:
    # 1. 规划
    state = run_planner(state)

    # 2. 三个研究节点并发
    trend_state, competitor_state, review_state = await asyncio.gather(
        run_trend_research(_make_child_state(state), search_fn=search_fn),
        run_competitor_analysis(_make_child_state(state), search_fn=search_fn),
        run_review_insight(_make_child_state(state), search_fn=search_fn),
    )

    # 合并研究结果与各自日志
    state["trend_result"] = trend_state["trend_result"]
    state["competitor_result"] = competitor_state["competitor_result"]
    state["review_result"] = review_state["review_result"]
    state["audit_log"].extend(trend_state["audit_log"])
    state["audit_log"].extend(competitor_state["audit_log"])
    state["audit_log"].extend(review_state["audit_log"])
    state["errors"].extend(trend_state["errors"])
    state["errors"].extend(competitor_state["errors"])
    state["errors"].extend(review_state["errors"])

    # 3. 汇总评分
    state = run_opportunity_scoring(state)
    # 4. 写报告
    state = run_report_writer(state)
    # 5. 质量检查
    state = run_quality_review(state)
    return state
