"""
EcomResearcher 工作流编排（LangGraph StateGraph 版，含全链路日志）。

【正经注释】
用 langgraph 的 StateGraph 把 7 个 Agent 编排成一张图：
START → planner → {trend, competitor, review}(fork-join 并发) → scoring → writer → quality → END
- trend/competitor/review 三条边都从 planner 出、都进 scoring，langgraph 在一个 superstep
  内并发跑这三者，scoring 自动 barrier 等三者完成（原生 fork-join）。
- audit_log/errors 用 Annotated[list, operator.add] reducer，三分支各自返回的增量由图自动拼接。
- governance 【不】放进任何 node 的返回值（plain channel 并发写会触发 InvalidUpdateError），
  改由 build_ecommerce_graph 闭包捕获 state["governance"] 同一对象，各 agent 通过 budget_manager /
  record_event 原地修改；run_ecommerce_graph 结尾再把该对象赋回 final["governance"] 兜底。
- 每个 node 在 fresh [] 的 audit_log/errors 上 append，只返回【增量】，保证 reducer 不重复累加。
- review 节点额外接收 llm_fn（中文归纳）与 budget_manager（外部 API 计费）。
每个阶段切换时既向外推送 progress_callback（WebSocket 流式），也写入 logger（落到
logs/ecommerce/<ts>_<query>.log）。

【大白话注释】
现在真的是一张 langgraph 图了：规划完，趋势/竞品/评论三路【由图并发】跑（不是手写 gather），
评分节点自动等三路都回来再开工。日志和错误列声明成「自动累加」，三路各写各的会被图拼起来。
治理账本（governance）不走图的通道（并发写会打架），而是大家共用闭包里的同一个对象。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Literal

from langgraph.graph import END, START, StateGraph

from multi_agents.ecommerce.agents.competitor_analyzer import run_competitor_analysis
from multi_agents.ecommerce.agents.opportunity_scorer import run_opportunity_scoring
from multi_agents.ecommerce.agents.planner import run_planner
from multi_agents.ecommerce.agents.quality_reviewer import run_quality_review
from multi_agents.ecommerce.agents.report_writer import run_report_writer
from multi_agents.ecommerce.agents.review_insight import run_review_insight
from multi_agents.ecommerce.agents.trend_researcher import run_trend_research
from multi_agents.ecommerce.llm_helper import LlmFn
from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
from multi_agents.ecommerce.runtime.execution_guard import ExecutionGuard
from multi_agents.ecommerce.state import EcommerceGraphState, EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, make_budgeted_search_fn

logger = logging.getLogger("multi_agents.ecommerce")

# 阶段进度回调：(event, payload) -> None
ProgressFn = Callable[[str, dict], Awaitable[None]]


def _fresh_child(
    state: dict, governance: dict[str, object]
) -> dict[str, object]:
    """构造 node 用的子状态：继承只读/前置字段，fresh audit_log/errors，governance 用闭包共享引用。

    【正经注释】
    关键：每个 node 都在【全新空】的 audit_log/errors 上 append，最后只把这两份【增量】返回，
    由 EcommerceGraphState 的 Annotated[list, operator.add] reducer 自动拼接，避免全量返回导致的
    重复累加。governance 用闭包捕获的同一对象（绝不来自 state channel），保证并发分支写的事件
    都落到同一账本。

    【大白话注释】
    每个节点开工前领一本「空白日志本」，干完只把这本新写的几行交上去，图自动把它们订在一起。
    治理账本则是大家共用闭包里那一本（不能走图的通道，否则并发写会报错）。
    """
    return {**state, "audit_log": [], "errors": [], "governance": governance}


def _failed_child_state(
    state: dict,
    governance: dict[str, object],
    *,
    agent: str,
    result_key: Literal["trend_result", "competitor_result", "review_result"],
    exc: Exception,
) -> dict[str, object]:
    """构造单个并发研究节点失败后的 partial 子状态（不重复记 governance failure，guard 已记）。"""
    child = _fresh_child(state, governance)
    # 失败分支：各维度置低分（2.0）+ data_failed 标志，避免下游 scoring 按
    # .get(*_score, 4.0) 默认值算出"看似有依据"的评分，掩盖数据源失败。
    _FAIL_SCORE_FIELD = {
        "trend_result": "trend_score",
        "competitor_result": "competition_score",
        "review_result": "pain_point_score",
    }
    failed: dict[str, object] = {
        "summary": "",
        "evidence": [],
        "confidence": 0.0,
        "error": str(exc),
        "data_failed": True,
    }
    score_field = _FAIL_SCORE_FIELD.get(result_key)
    if score_field is not None:
        failed[score_field] = 2.0
    child[result_key] = failed
    child["audit_log"].append(
        {
            "agent": agent,
            "status": "partial",
            "duration_ms": 0,
            "source_count": 0,
            "confidence": 0.0,
            "warning": str(exc),
        }
    )
    child["errors"].append({"agent": agent, "error": str(exc)})
    return child


def build_ecommerce_graph(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
    llm_fn: LlmFn | None = None,
    progress_callback: ProgressFn | None = None,
    budget_manager: BudgetManager | None = None,
):
    """根据本次运行的依赖构建并 compile langgraph StateGraph。

    依赖（search_fn/llm_fn/budget_manager/progress_callback/governance）通过闭包注入各 node，
    不进 state schema。返回 compiled graph，可 `.ainvoke(state)`。
    """
    governance = state["governance"]
    guard = ExecutionGuard(governance)

    async def _emit(event: str, payload: dict | None = None) -> None:
        msg = f"[graph] {event}" + (f" {payload}" if payload else "")
        logger.info(msg)
        if progress_callback is not None:
            try:
                await progress_callback(event, payload or {})
            except Exception:
                logger.warning(f"[graph] progress_callback 推送失败 event={event}")

    # ---- 规划节点（同步 agent）---- 发 start / planner_done / research_running
    async def planner_node(s: dict) -> dict:
        await _emit("start", {"query": s.get("query"), "market": s.get("target_market")})
        child = _fresh_child(s, governance)
        out = run_planner(child)  # 同步
        await _emit(
            "planner_done",
            {"queries": len(out.get("research_plan", {}).get("trend_queries", []))},
        )
        # research_running 在 planner 末尾发【一次】，而不是每个 research 节点发
        await _emit("research_running", {"agents": ["trend", "competitor", "review"]})
        return {
            "research_plan": out.get("research_plan", {}),
            "audit_log": out["audit_log"],
        }

    # ---- 通用并发研究节点 ---- guard 包裹 + 失败转 partial（不连坐其它分支）
    async def _research_node(
        agent_name: str,
        result_key: str,
        run_fn: Callable[..., Awaitable[EcommerceResearchState]],
        extra_kwargs: dict,
        s: dict,
    ) -> dict:
        child = _fresh_child(s, governance)
        branch_search_fn = make_budgeted_search_fn(
            search_fn, budget_manager, agent_name=agent_name
        )
        try:
            # run_fn 用 bare name 传入（trend_node 等传 run_trend_research 全局名），
            # 便于测试 monkeypatch.setattr(graph_mod, "run_trend_research", ...)
            res = await guard.run(
                name=agent_name,
                operation=lambda: run_fn(child, search_fn=branch_search_fn, **extra_kwargs),
                timeout_ms=120_000,
                max_retries=0,
            )
        except Exception as exc:
            logger.error(f"[graph] {agent_name} failed under execution guard: {exc}")
            res = _failed_child_state(
                s, governance, agent=agent_name, result_key=result_key, exc=exc
            )
        return {
            result_key: res[result_key],
            "audit_log": res["audit_log"],
            "errors": res["errors"],
        }

    async def trend_node(s: dict) -> dict:
        # run_trend_research 为 module 全局名，运行时解析，支持 monkeypatch
        return await _research_node(
            "TrendResearchAgent", "trend_result", run_trend_research, {"llm_fn": llm_fn}, s
        )

    async def competitor_node(s: dict) -> dict:
        return await _research_node(
            "CompetitorAnalysisAgent",
            "competitor_result",
            run_competitor_analysis,
            {"llm_fn": llm_fn},
            s,
        )

    async def review_node(s: dict) -> dict:
        return await _research_node(
            "ReviewInsightAgent",
            "review_result",
            run_review_insight,
            {"llm_fn": llm_fn, "budget_manager": budget_manager},
            s,
        )

    # ---- 评分节点（async, LLM 优先）---- 发 research_done / scoring_done
    async def scoring_node(s: dict) -> dict:
        await _emit(
            "research_done",
            {
                "trend_sources": len(s.get("trend_result", {}).get("evidence", [])),
                "competitor_sources": len(s.get("competitor_result", {}).get("evidence", [])),
                "review_sources": len(s.get("review_result", {}).get("evidence", [])),
            },
        )
        child = _fresh_child(s, governance)
        out = await run_opportunity_scoring(
            child, llm_fn=llm_fn, budget_manager=budget_manager
        )
        await _emit(
            "scoring_done",
            {
                "overall_score": out["opportunity_score"].get("overall_score"),
                "scored_by": out["opportunity_score"].get("scored_by"),
                "recommendation": out["opportunity_score"].get("recommendation"),
            },
        )
        return {"opportunity_score": out["opportunity_score"], "audit_log": out["audit_log"]}

    # ---- 写报告节点（同步）---- 发 report_done
    async def writer_node(s: dict) -> dict:
        child = _fresh_child(s, governance)
        out = run_report_writer(child)
        await _emit("report_done", {})
        return {"final_report": out["final_report"], "audit_log": out["audit_log"]}

    # ---- 质检节点（同步）---- 发 quality_done
    async def quality_node(s: dict) -> dict:
        child = _fresh_child(s, governance)
        out = run_quality_review(child)
        await _emit("quality_done", {"passed": out["quality_check"].get("passed")})
        return {"quality_check": out["quality_check"], "audit_log": out["audit_log"]}

    wf = StateGraph(EcommerceGraphState)
    wf.add_node("planner", planner_node)
    wf.add_node("trend", trend_node)
    wf.add_node("competitor", competitor_node)
    wf.add_node("review", review_node)
    wf.add_node("scoring", scoring_node)
    wf.add_node("writer", writer_node)
    wf.add_node("quality", quality_node)

    wf.add_edge(START, "planner")
    # fork：planner → 三路并发
    wf.add_edge("planner", "trend")
    wf.add_edge("planner", "competitor")
    wf.add_edge("planner", "review")
    # join：三路全部完成后才进入 scoring（显式 barrier join）
    wf.add_edge(["trend", "competitor", "review"], "scoring")
    wf.add_edge("scoring", "writer")
    wf.add_edge("writer", "quality")
    wf.add_edge("quality", END)
    return wf.compile()


async def run_ecommerce_graph(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
    llm_fn: LlmFn | None = None,
    progress_callback: ProgressFn | None = None,
    budget_manager: BudgetManager | None = None,
) -> EcommerceResearchState:
    """跑完整的 langgraph 选品工作流，返回最终状态。

    签名与历史一致（test_ecommerce_runner.test_graph_records_failure_when_parallel_agent_raises
    直接调用 + monkeypatch run_trend_research 等模块级名）。内部 build + compile + ainvoke。
    """
    app = build_ecommerce_graph(
        state,
        search_fn=search_fn,
        llm_fn=llm_fn,
        progress_callback=progress_callback,
        budget_manager=budget_manager,
    )
    final = await app.ainvoke(state, config={"recursion_limit": 25})
    # governance 全程靠闭包共享引用原地修改；这里兜底确保返回的就是那个对象
    final["governance"] = state["governance"]
    return final
