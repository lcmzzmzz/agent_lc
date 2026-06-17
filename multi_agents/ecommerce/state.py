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

from typing import Any, TypedDict


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
    }
