"""LangGraph 迁移后的拓扑 / 并发 / governance 契约测试。

这些测试证明 graph.py 真的使用了 langgraph StateGraph（原生 fork-join + reducer），
而非手写 asyncio。是「基于 LangGraph」这一简历表述的物证。
"""

import asyncio

import pytest

from multi_agents.ecommerce import graph as graph_mod
from multi_agents.ecommerce.graph import build_ecommerce_graph, run_ecommerce_graph
from multi_agents.ecommerce.runtime.telemetry import record_event, summarize_governance
from multi_agents.ecommerce.state import create_initial_state


def _fake_search(query, max_results):
    return [{"title": "T", "href": "https://example.com/x", "body": "battery life $30"}]


def _ok_branch(result_key, agent):
    """构造一个「正常完成」的 fake 研究 agent：写 result + 记一条 audit。"""

    async def fn(child, *, search_fn, llm_fn=None, budget_manager=None):
        child[result_key] = {"summary": agent, "evidence": [], "confidence": 0.5}
        child["audit_log"].append({"agent": agent, "marker": agent})
        return child

    return fn


# ---------------------------------------------------------------------------
# 1. 拓扑：真是 langgraph compiled StateGraph，含 7 个 node
# ---------------------------------------------------------------------------


def test_graph_is_compiled_stategraph():
    state = create_initial_state("portable blender")
    app = build_ecommerce_graph(state, search_fn=_fake_search)

    assert hasattr(app, "get_graph"), "compiled graph 应暴露 get_graph()"
    nodes = set(app.get_graph().nodes.keys())
    for name in ("planner", "trend", "competitor", "review", "scoring", "writer", "quality"):
        assert name in nodes, f"图里缺 node: {name}"


# ---------------------------------------------------------------------------
# 2. fork-join 真并发（三条研究分支同时活跃）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_branches_run_concurrently(monkeypatch):
    counter = {"active": 0, "max_active": 0}

    def branch(name):
        async def fn(child, *, search_fn, llm_fn=None, budget_manager=None):
            counter["active"] += 1
            counter["max_active"] = max(counter["max_active"], counter["active"])
            await asyncio.sleep(0.05)
            counter["active"] -= 1
            child[f"{name}_result"] = {"summary": name, "evidence": [], "confidence": 0.5}
            child["audit_log"].append({"agent": name})
            return child

        return fn

    monkeypatch.setattr(graph_mod, "run_trend_research", branch("trend"))
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", branch("competitor"))
    monkeypatch.setattr(graph_mod, "run_review_insight", branch("review"))

    state = create_initial_state("portable blender")
    await run_ecommerce_graph(state, search_fn=_fake_search)

    assert counter["max_active"] >= 2, (
        f"研究分支未并发执行（max_active={counter['max_active']}），langgraph fork-join 假设不成立"
    )


# ---------------------------------------------------------------------------
# 3. governance 跨并发 review 分支生存（review 写的 fallback 事件到得了 final）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_governance_events_survive_concurrent_review_branch(monkeypatch):
    async def review_writes_fallback(child, *, search_fn, llm_fn=None, budget_manager=None):
        record_event(
            child["governance"],
            kind="fallback",
            agent="ReviewInsightAgent",
            detail="apify returned 0 reviews",
            fallback_used=True,
        )
        child["review_result"] = {"summary": "review", "evidence": [], "confidence": 0.5}
        child["audit_log"].append({"agent": "ReviewInsightAgent"})
        return child

    monkeypatch.setattr(graph_mod, "run_trend_research", _ok_branch("trend_result", "TrendResearchAgent"))
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", _ok_branch("competitor_result", "CompetitorAnalyzerAgent"))
    monkeypatch.setattr(graph_mod, "run_review_insight", review_writes_fallback)

    state = create_initial_state("portable blender")
    final = await run_ecommerce_graph(state, search_fn=_fake_search)

    assert summarize_governance(final["governance"])["fallback_count"] == 1


# ---------------------------------------------------------------------------
# 4. 7 个 progress 事件按 WS 契约顺序推送
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_eight_progress_events_emitted_in_order(monkeypatch):
    events = []

    async def progress(event, payload):
        events.append(event)

    monkeypatch.setattr(graph_mod, "run_trend_research", _ok_branch("trend_result", "T"))
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", _ok_branch("competitor_result", "C"))
    monkeypatch.setattr(graph_mod, "run_review_insight", _ok_branch("review_result", "R"))

    state = create_initial_state("portable blender")
    await run_ecommerce_graph(state, search_fn=_fake_search, progress_callback=progress)

    expected = [
        "start",
        "planner_done",
        "research_running",
        "research_done",
        "scoring_done",
        "report_done",
        "quality_done",
    ]
    assert events == expected, f"progress 事件序列不符: {events}"


# ---------------------------------------------------------------------------
# 5. fork-join 把三分支的 audit_log 增量全合并
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fork_join_merges_audit_log_from_three_branches(monkeypatch):
    monkeypatch.setattr(graph_mod, "run_trend_research", _ok_branch("trend_result", "TrendResearchAgent"))
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", _ok_branch("competitor_result", "CompetitorAnalyzerAgent"))
    monkeypatch.setattr(graph_mod, "run_review_insight", _ok_branch("review_result", "ReviewInsightAgent"))

    state = create_initial_state("portable blender")
    final = await run_ecommerce_graph(state, search_fn=_fake_search)

    markers = {e.get("marker") for e in final["audit_log"] if e.get("marker")}
    assert markers == {"TrendResearchAgent", "CompetitorAnalyzerAgent", "ReviewInsightAgent"}, (
        f"三分支 audit_log 未全部合并: {markers}"
    )


# ---------------------------------------------------------------------------
# 6. 单分支失败不连坐（另两分支仍完成，失败分支转 partial）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_node_failure_does_not_abort_graph(monkeypatch):
    async def fail_trend(child, *, search_fn, llm_fn=None):
        raise RuntimeError("trend boom")

    monkeypatch.setattr(graph_mod, "run_trend_research", fail_trend)
    monkeypatch.setattr(graph_mod, "run_competitor_analysis", _ok_branch("competitor_result", "CompetitorAnalyzerAgent"))
    monkeypatch.setattr(graph_mod, "run_review_insight", _ok_branch("review_result", "ReviewInsightAgent"))

    state = create_initial_state("portable blender")
    final = await run_ecommerce_graph(state, search_fn=_fake_search)

    markers = {e.get("marker") for e in final["audit_log"] if e.get("marker")}
    assert "CompetitorAnalyzerAgent" in markers
    assert "ReviewInsightAgent" in markers
    assert final["trend_result"]["summary"] == ""  # 失败分支转 partial
    assert summarize_governance(final["governance"])["failure_count"] == 1


# ---------------------------------------------------------------------------
# 7. module-level agent 名仍可被 monkeypatch（linchpin 契约防护）
# ---------------------------------------------------------------------------


def test_module_level_agent_imports_remain_patchable():
    for name in ("run_trend_research", "run_competitor_analysis", "run_review_insight"):
        assert hasattr(graph_mod, name), f"{name} 不在 graph 模块级，monkeypatch 契约会断"
