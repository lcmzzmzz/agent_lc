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
    """
    选品调研规划（同步）。

    【正经注释】
    纯本地计算，不触网、不调 LLM：按 depth 取 max_queries，用 build_ecommerce_queries
    生成 trend/competitor/review 三类查询（对应图中三条并发研究分支），并固定 risk_focus
    与 scoring_dimensions 两个契约字段供下游评分/质检消费，最后记审计。

    【大白话注释】
    给后面干活的人"派活清单"：
    - 三类搜索关键词（趋势/竞品/评论）→ 交给三路人马去搜
    - 风险关注点 → 告诉大家重点防哪几类坑
    - 评分维度 → 提前定好最后打分打哪几项
    自己不联网、不花钱，所以又快又稳。
    """
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    max_queries = config["max_queries_per_agent"]

    query = state["query"]
    market = state["target_market"]

    # 【正经注释】research_plan 是下游三个并发研究节点的输入契约：
    #   trend_queries→trend 节点、competitor_queries→competitor 节点、review_queries→review 节点；
    #   max_queries 受 depth 档位控制（fast=2 / standard=4 / deep=6）。
    #   risk_focus / scoring_dimensions 是给评分与质检环节用的契约，不是拿去检索的。
    # 【大白话注释】下面这张"清单"分两半：前三类是搜索词，分给三路人马；
    #   后两项（盯什么风险、最后打哪几分）是给打分和质检的人看的，不用去搜。
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

    # 【正经注释】planner 不触网检索，故 source_count=0；逻辑确定性强，confidence=1.0。
    # 【大白话注释】记一笔审计：这一步没搜外部、没花钱，稳稳完成。
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
