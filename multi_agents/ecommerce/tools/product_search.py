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
        "{query} customer complaints",
        "{query} amazon reviews",
        "{query} negative reviews",
        "{query} reddit review",
        "{query} pros and cons",
        "{query} customer feedback",
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
