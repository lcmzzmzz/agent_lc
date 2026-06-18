"""
EcomResearcher 工作流的共享状态定义。

【正经注释】
定义顶层研究状态 EcommerceResearchState，以及标准化数据源 EcommerceSource。
采用 TypedDict(total=False) 以兼容 Python 3.10 并允许字段按节点逐步填充。
每个 Agent 只读写自己负责的字段，节点之间通过该状态流转数据。

【大白话注释】
这个文件定义了"整条选品流程的共享小本本"。
各个 Agent（趋势、竞品、评论、评分、写作、审查）各写各的字段，
后面的 Agent 直接从小本本上读就行。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from multi_agents.ecommerce.runtime.telemetry import empty_governance_state


class EcommerceSource(TypedDict, total=False):
    """标准化后的单一数据源。"""

    title: str
    url: str
    source_type: str  # amazon | google | reddit | blog | review_site | social
    snippet: str
    content: str


class AgentResult(TypedDict, total=False):
    """单个研究 Agent 的通用结果结构（趋势/竞品/评论共用语义）。"""

    summary: str
    key_findings: list[str]
    evidence: list[EcommerceSource]
    confidence: float
    error: str


class EcommerceResearchState(TypedDict, total=False):
    """整条选品工作流的共享状态。"""

    # ── 输入 ──
    query: str
    target_market: str
    platforms: list[str]
    depth: str  # fast | standard | deep

    # ── 规划与研究结果 ──
    research_plan: dict[str, Any]
    trend_result: dict[str, Any]
    competitor_result: dict[str, Any]
    review_result: dict[str, Any]

    # ── 评分与输出 ──
    opportunity_score: dict[str, Any]
    final_report: str
    quality_check: dict[str, Any]

    # ── 可观测性 ──
    audit_log: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    output_paths: dict[str, str]
    governance: dict[str, Any]


class EcommerceGraphState(TypedDict, total=False):
    """LangGraph StateGraph 用的状态契约（graph 专用，agent 仍用 EcommerceResearchState）。

    【正经注释】
    与 EcommerceResearchState 字段一致，但 audit_log/errors 标注了 Annotated[list, operator.add]
    reducer —— fork-join 的三个并发研究分支（trend/competitor/review）各自返回的增量会被 langgraph
    自动拼接，无需手动 extend。governance 保持 plain channel：节点不返回它（并发写 plain channel
    会触发 InvalidUpdateError），改由 closure 捕获同一 dict 引用原地修改。research/scoring 等
    「单写者」结果字段仍是 plain channel（last-write-wins 安全）。

    【大白话注释】
    给 langgraph 图用的状态表：日志/错误列改成「自动累加」，并发分支各写各的会被图自动合并；
    governance 列只是占位（实际靠闭包共享同一个对象改，不走图的 channel，否则并发写会打架）。
    """

    # ── 输入（只读）──
    query: str
    target_market: str
    platforms: list[str]
    depth: str
    research_plan: dict[str, Any]

    # ── 单写者结果（plain channel）──
    trend_result: dict[str, Any]
    competitor_result: dict[str, Any]
    review_result: dict[str, Any]
    opportunity_score: dict[str, Any]
    final_report: str
    quality_check: dict[str, Any]

    # ── 累加器（reducer 合并并发分支）──
    audit_log: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]

    # ── governance（plain channel，靠 closure 共享引用，节点不返回）──
    governance: dict[str, Any]


def create_initial_state(
    query: str,
    target_market: str = "US",
    platforms: list[str] | None = None,
    depth: str = "standard",
) -> EcommerceResearchState:
    """构造初始状态。

    【正经注释】
    填充用户输入字段，并把可变集合字段初始化为空，避免后续节点对 None 做处理。

    【大白话注释】
    把用户给的信息记到小本本上，顺便把后面要用的空格子都先准备好。
    """
    return {
        "query": query,
        "target_market": target_market,
        "platforms": platforms or ["amazon", "google"],
        "depth": depth,
        "research_plan": {},
        "trend_result": {},
        "competitor_result": {},
        "review_result": {},
        "opportunity_score": {},
        "final_report": "",
        "quality_check": {},
        "audit_log": [],
        "errors": [],
        "governance": empty_governance_state(),
    }
