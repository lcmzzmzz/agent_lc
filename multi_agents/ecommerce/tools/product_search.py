"""
商品搜索工具：构造查询 + 调用注入的检索函数。

【正经注释】
build_ecommerce_queries 按调研意图（trend/competitor/review/risk）生成模板查询；
search_sources 接收注入的异步检索函数 SearchFn，逐条查询并标准化、去重。
"注入 search_fn" 是为了让测试能用 fake_search 替换真实网络检索。

【大白话注释】
两件事：一是按"趋势/竞品/评论/风险"凑出一批搜索关键词；
二是拿着这些关键词去搜（搜什么由外面传进来，测试时换成假的），
搜到的结果整理整齐、去重，再交出去。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
from multi_agents.ecommerce.state import EcommerceSource
from multi_agents.ecommerce.tools.source_normalizer import normalize_source

# 注入的检索函数签名：(query, max_results) -> list[原始结果dict]
SearchFn = Callable[[str, int], Awaitable[list[dict[str, Any]]]]


# 各意图的查询模板，{query}/{market} 会被实际关键词替换
_QUERY_TEMPLATES: dict[str, list[str]] = {
    "trend": [
        "{query} market trend {market}",
        "{query} demand seasonality {market}",
        "{query} google trends {market}",
        "{query} consumer trend report",
        "{query} market growth",
        "{query} industry analysis",
    ],
    "competitor": [
        "{query} amazon best sellers",
        "{query} top products amazon",
        "{query} best {query} reviews",
        "{query} price comparison",
        "{query} competitors",
        "{query} product comparison",
    ],
    "review": [
        "{query} customer complaints {market}",
        "{query} amazon reviews {market}",
        "{query} negative reviews {market}",
        "{query} reddit review {market}",
        "{query} pros and cons {market}",
        "{query} customer feedback {market}",
    ],
    "risk": [
        "{query} safety issues",
        "{query} compliance risk",
        "{query} shipping damage complaints",
        "{query} warranty complaints",
    ],
}


def build_ecommerce_queries(
    *,
    query: str,
    target_market: str,
    intent: str,
    max_queries: int,
) -> list[str]:
    """按意图生成最多 max_queries 条查询。未知意图回退到 trend。"""
    templates = _QUERY_TEMPLATES.get(intent, _QUERY_TEMPLATES["trend"])
    return [
        item.format(query=query, market=target_market)
        for item in templates[:max_queries]
    ]


async def search_sources(
    *,
    queries: list[str],
    search_fn: SearchFn,
    max_results_per_query: int,
) -> list[EcommerceSource]:
    """对每条查询调用 search_fn，汇总、标准化并按 url 去重。"""
    sources: list[EcommerceSource] = []
    seen_urls: set[str] = set()

    for query in queries:
        raw_results = await search_fn(query, max_results_per_query)
        for raw in raw_results:
            source = normalize_source(raw)
            url = source.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            sources.append(source)

    return sources


def make_budgeted_search_fn(
    search_fn: SearchFn, budget_manager: BudgetManager | None
) -> SearchFn:
    """把 search_fn 包一层预算闸门。

    【正经注释】每次调用前查 budget_manager.can_use('search')：超预算则直接返回 []，
    并通过 record_degradation 在 governance 上标记降级，保证审计可见；未超则 record 后放行。
    budget_manager 为 None 时（兼容旧调用/无治理态）退化为透传。

    【大白话注释】给搜索函数装个"用量计数器 + 闸门"——没超额度就放行并 +1，
    超了就立刻返回空结果、并在治理日志里记一笔降级，省得搜索把预算烧光。
    """

    async def wrapped(query: str, max_results: int) -> list[dict[str, Any]]:
        if budget_manager is not None:
            if not budget_manager.can_use("search"):
                budget_manager.record_degradation("SearchFn", "search budget exceeded")
                return []
            budget_manager.record("search")
        return await search_fn(query, max_results)

    return wrapped
