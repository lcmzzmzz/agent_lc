"""
EcomResearcher 工作流编排（含全链路日志）。

【正经注释】
run_ecommerce_graph 把 7 个 Agent 串成一条流水线：
planner(同步) → [trend, competitor, review] 并发 → opportunity_scoring(LLM优先) →
report_writer → quality_reviewer。
每个阶段切换时既向外推送 progress_callback（WebSocket 流式），
也写入 multi_agents.ecommerce logger（落到 logs/ecommerce/<ts>_<query>.log）。
review 节点额外接收 llm_fn，用于把英文评论归纳为中文痛点。

【大白话注释】
把 7 个角色按顺序连起来，每走完一个大阶段就"喊一声"：
既实时推给前端，也记到这次研究的专属日志文件里。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from multi_agents.ecommerce.agents.competitor_analyzer import run_competitor_analysis
from multi_agents.ecommerce.agents.opportunity_scorer import run_opportunity_scoring
from multi_agents.ecommerce.agents.planner import run_planner
from multi_agents.ecommerce.agents.quality_reviewer import run_quality_review
from multi_agents.ecommerce.agents.report_writer import run_report_writer
from multi_agents.ecommerce.agents.review_insight import run_review_insight
from multi_agents.ecommerce.agents.trend_researcher import run_trend_research
from multi_agents.ecommerce.llm_helper import LlmFn
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn

logger = logging.getLogger("multi_agents.ecommerce")

# 阶段进度回调：(event, payload) -> None
ProgressFn = Callable[[str, dict], Awaitable[None]]


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
    llm_fn: LlmFn | None = None,
    progress_callback: ProgressFn | None = None,
) -> EcommerceResearchState:
    async def _emit(event: str, payload: dict | None = None) -> None:
        msg = f"[graph] {event}" + (f" {payload}" if payload else "")
        logger.info(msg)
        if progress_callback is not None:
            try:
                await progress_callback(event, payload or {})
            except Exception:
                logger.warning(f"[graph] progress_callback 推送失败 event={event}")

    await _emit("start", {"query": state["query"], "market": state["target_market"]})

    # 1. 规划
    state = run_planner(state)
    await _emit(
        "planner_done",
        {"queries": len(state["research_plan"].get("trend_queries", []))},
    )

    # 2. 三个研究节点并发（review 额外接收 llm_fn 做中文归纳）
    await _emit("research_running", {"agents": ["trend", "competitor", "review"]})
    trend_state, competitor_state, review_state = await asyncio.gather(
        run_trend_research(_make_child_state(state), search_fn=search_fn, llm_fn=llm_fn),
        run_competitor_analysis(_make_child_state(state), search_fn=search_fn, llm_fn=llm_fn),
        run_review_insight(_make_child_state(state), search_fn=search_fn, llm_fn=llm_fn),
    )

    state["trend_result"] = trend_state["trend_result"]
    state["competitor_result"] = competitor_state["competitor_result"]
    state["review_result"] = review_state["review_result"]
    state["audit_log"].extend(trend_state["audit_log"])
    state["audit_log"].extend(competitor_state["audit_log"])
    state["audit_log"].extend(review_state["audit_log"])
    state["errors"].extend(trend_state["errors"])
    state["errors"].extend(competitor_state["errors"])
    state["errors"].extend(review_state["errors"])
    await _emit(
        "research_done",
        {
            "trend_sources": len(state["trend_result"].get("evidence", [])),
            "competitor_sources": len(state["competitor_result"].get("evidence", [])),
            "review_sources": len(state["review_result"].get("evidence", [])),
        },
    )

    # 3. 汇总评分（LLM 优先，规则兜底）
    state = await run_opportunity_scoring(state, llm_fn=llm_fn)
    await _emit(
        "scoring_done",
        {
            "overall_score": state["opportunity_score"].get("overall_score"),
            "scored_by": state["opportunity_score"].get("scored_by"),
            "recommendation": state["opportunity_score"].get("recommendation"),
        },
    )

    # 4. 写报告
    state = run_report_writer(state)
    await _emit("report_done", {})

    # 5. 质量检查
    state = run_quality_review(state)
    await _emit("quality_done", {"passed": state["quality_check"].get("passed")})
    return state
