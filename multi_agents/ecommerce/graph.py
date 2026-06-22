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
    # 复制当前 state，但：audit_log/errors 清空（让节点在「空白本」上写、只返回增量，
    # 配合 Annotated[list, operator.add] reducer 自动拼接，避免重复累加）；
    # governance 换成闭包共享的那个引用（绝不来自 state channel，避免并发写冲突）
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
    *,                              # ← 单独的 * 是「关键字参数分隔符」：之后的参数调用时必须用关键字传（防传串）
    search_fn: SearchFn,            # 检索函数（生产=Tavily，测试=fake_search）—— 靠闭包注入节点，不进 state
    llm_fn: LlmFn | None = None,    # 大模型函数（None=全程不调 LLM，走规则）
    progress_callback: ProgressFn | None = None,  # 前端进度回调（None=无前端/测试）
    budget_manager: BudgetManager | None = None,  # 预算管家（None=不控预算）
):
    """根据本次运行的依赖构建并 compile langgraph StateGraph。

    依赖（search_fn/llm_fn/budget_manager/progress_callback/governance）通过闭包注入各 node，
    不进 state schema。返回 compiled graph，可 `.ainvoke(state)`。
    """
    # 下面这两样会被【所有节点闭包捕获】——这是整个图「依赖注入 + 治理共享」的起点
    governance = state["governance"]      # 从入口 state 拿 governance 引用（闭包共享的起点）
    guard = ExecutionGuard(governance)    # 执行护栏（超时/重试/兜底），拿同一个 governance 引用

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
        # s = langgraph 运行时注入的「当前 state」（节点签名约定：第一个参数永远是当前 state）
        await _emit("start", {"query": s.get("query"), "market": s.get("target_market")})
        child = _fresh_child(s, governance)  # 复制 s + 清空日志本 + 换上闭包的 governance
        out = run_planner(child)  # 同步调 planner，生成 trend/competitor/review 的 sub-queries
        print(f'planner_node:out: {out}')
        await _emit(
            "planner_done",
            {"queries": len(out.get("research_plan", {}).get("trend_queries", []))},
        )
        # research_running 在 planner 末尾发【一次】，而不是每个 research 节点发
        await _emit("research_running", {"agents": ["trend", "competitor", "review"]})
        # 节点只返回【要更新的字段】（不是整个 state）；langgraph 拿这个 dict 合并进 state：
        # research_plan 是 plain channel（覆盖）；audit_log 挂 operator.add reducer（与现有拼接）
        return {
            "research_plan": out.get("research_plan", {}),
            "audit_log": out["audit_log"],
        }

    # ---- 通用并发研究节点（模板）---- trend/competitor/review 三路都调它，只是填不同参数 ----
    # guard 包裹 + 失败转 partial（不连坐其它分支）
    async def _research_node(
        agent_name: str,            # 代理名（如 "TrendResearchAgent"，用于 audit/事件）
        result_key: str,            # 结果写进 state 的哪个键（"trend_result" / "competitor_result" / "review_result"）
        run_fn: Callable[..., Awaitable[EcommerceResearchState]],  # 真正干活的 agent 函数（run_trend_research 等）
        extra_kwargs: dict,         # 传给 run_fn 的额外参数（如 {"llm_fn": llm_fn}）
        s: dict,                    # langgraph 注入的当前 state
    ) -> dict:
        child = _fresh_child(s, governance)  #拿到state 副本
        # make_budgeted_search_fn：工厂返回一个【闭包】，把裸 search_fn 包成「带预算闸门 + agent 身份」的搜索函数
        branch_search_fn = make_budgeted_search_fn(
            search_fn, budget_manager, agent_name=agent_name
        )
        try:
            # run_fn 用 bare name 传入（trend_node 等传 run_trend_research 全局名），
            # 便于测试 monkeypatch.setattr(graph_mod, "run_trend_research", ...)
            # guard.run：执行保镖包住 operation——超时 120s 掐掉、可重试、可兜底；所有结果写进 governance
            # operation=lambda:... 是个【闭包】，把 child/run_fn/branch_search_fn 打包成无参可调用对象交给 guard
            res = await guard.run(
                name=agent_name,
                operation=lambda: run_fn(child, search_fn=branch_search_fn, **extra_kwargs),
                timeout_ms=120_000,
                max_retries=0,
            )
        except Exception as exc:
            # ⚠️ 失败不连坐：这一路挂了转 partial（低分 2.0 + data_failed），另外两路照跑、评分诚实降分
            logger.error(f"[graph] {agent_name} failed under execution guard: {exc}")
            res = _failed_child_state(
                s, governance, agent=agent_name, result_key=result_key, exc=exc
            )
        # 只返回增量字段；audit_log/errors 靠 reducer 与现有拼接，governance 不在这里返回（走闭包）
        print(f'{agent_name}:out: {res}')
        return {
            result_key: res[result_key],
            "audit_log": res["audit_log"],
            "errors": res["errors"],
        }

    # ---- 三路并发研究节点 ---- 只是往 _research_node 模板填不同参数 ----
    # 三路的「并发」不是这里写 asyncio.gather，而是靠下面 add_edge 把三者都连到 planner（fork）
    # 它们在一个 superstep 内由 langgraph 自动并发，scoring 那条 join 边自动 barrier 等三者
    async def trend_node(s: dict) -> dict:
        # run_trend_research 为 module 全局名，运行时解析，支持 monkeypatch
        return await _research_node(
            "TrendResearchAgent",
            "trend_result",
            run_trend_research,
            {"llm_fn": llm_fn},
            s
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
        # review 额外要 budget_manager：因为它可能调外部 API（Apify），需要单独计费
        return await _research_node(
            "ReviewInsightAgent",
            "review_result",
            run_review_insight,
            {"llm_fn": llm_fn, "budget_manager": budget_manager},
            s,
        )

    # ---- 评分节点（async, LLM 优先）---- 在 join barrier 之后跑（三路结果都已就绪）----
    # 发 research_done / scoring_done
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
        # LLM 优先打分；超预算/LLM 失败时 run_opportunity_scoring 内部自动降级为规则评分
        out = await run_opportunity_scoring(
            child, llm_fn=llm_fn, budget_manager=budget_manager
        )
        print(f'scoring_node:out: {out}')
        await _emit(
            "scoring_done",
            {
                "overall_score": out["opportunity_score"].get("overall_score"),
                "scored_by": out["opportunity_score"].get("scored_by"),
                "recommendation": out["opportunity_score"].get("recommendation"),
            },
        )
        return {"opportunity_score": out["opportunity_score"], "audit_log": out["audit_log"]}

    # ---- 写报告节点（同步）---- 把评分/趋势/竞品/评论拼成 Markdown 报告 ---- 发 report_done
    async def writer_node(s: dict) -> dict:
        child = _fresh_child(s, governance)
        out = run_report_writer(child)  # 同步：按固定章节拼报告 + 收集引用
        print(f'writer_node:out: {out}')
        await _emit("report_done", {})
        return {"final_report": out["final_report"], "audit_log": out["audit_log"]}

    # ---- 质检节点（同步）---- 检查引用覆盖/证据充分度/过度自信措辞 ---- 发 quality_done
    async def quality_node(s: dict) -> dict:
        child = _fresh_child(s, governance)
        out = run_quality_review(child)  # 同步：基于真实痛点判定风险披露是否充分
        print(f'quality_node:out: {out}')
        await _emit("quality_done", {"passed": out["quality_check"].get("passed")})
        return {"quality_check": out["quality_check"], "audit_log": out["audit_log"]}

    # ───────────────────────── 拼图：注册节点 + 连边 ─────────────────────────
    # 用【图专用】schema EcommerceGraphState（audit_log/errors 带 operator.add reducer，图专用）
    wf = StateGraph(EcommerceGraphState)
    wf.add_node("planner", planner_node)       # 注册：把上面定义的闭包节点函数绑到节点名
    wf.add_node("trend", trend_node)
    wf.add_node("competitor", competitor_node)
    wf.add_node("review", review_node)
    wf.add_node("scoring", scoring_node)
    wf.add_node("writer", writer_node)
    wf.add_node("quality", quality_node)

    wf.add_edge(START, "planner")              # 入口：图从 planner 开始
    # fork：同一个源（planner）连 3 条边 → langgraph 自动让 trend/competitor/review【并发】跑
    wf.add_edge("planner", "trend")
    wf.add_edge("planner", "competitor")
    wf.add_edge("planner", "review")
    # join：源传【列表】→ 显式 barrier：三路【全部】完成才进 scoring（原生 fork-join，不用手写 gather）
    wf.add_edge(["trend", "competitor", "review"], "scoring")
    wf.add_edge("scoring", "writer")           # 之后串行：评分→写报告→质检
    wf.add_edge("writer", "quality")
    wf.add_edge("quality", END)                # 出口
    return wf.compile()                        # 编译成可 .ainvoke(state) 的图


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
    app = build_ecommerce_graph(            # ① 装配 + compile 出图
        state,
        search_fn=search_fn,
        llm_fn=llm_fn,
        progress_callback=progress_callback,
        budget_manager=budget_manager,
    )
    final = await app.ainvoke(state, config={"recursion_limit": 25})  # ② 跑图（recursion_limit 防图死循环）
    # governance 全程靠闭包共享引用原地修改；这里兜底确保返回的就是那个对象
    final["governance"] = state["governance"]   # ③ 兜底：把闭包改过的 governance 赋回 final（确保不丢）
    return final
