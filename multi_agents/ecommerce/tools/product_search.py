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
from multi_agents.ecommerce.runtime.policy_guard import PolicyViolation, assert_tool_allowed
from multi_agents.ecommerce.runtime.telemetry import record_event
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
            # 【正经注释】Task 8：MCP 适配器归一化后的结果带 source_type="mcp" + tool_name/server_name
            # 两个溯源字段，但 source_normalizer.normalize_source 只产出 EcommerceSource 标准五字段
            # （title/url/source_type/snippet/content），会把这俩丢掉。这里在 normalize 之后补回，
            # 让后续 Agent 能区分「这条证据来自 MCP 哪个工具/哪个 server」。
            # 注意：raw 是 search_fn 返回的原始 dict（mcp_adapter 输出形状），source 是归一化后的；
            # 我们读 raw 的 tool_name/server_name（normalize_source 不会改 raw），写进 source。
            # 【大白话注释】MCP 来源的结果带「哪个工具给的、哪个服务给的」两个标签，
            # 普通的整理函数会把这俩扔掉，这里捡回来贴上，方便后面知道证据出处。
            if raw.get("source_type") == "mcp":
                source["source_type"] = "mcp"
                source["tool_name"] = raw.get("tool_name", "")
                source["server_name"] = raw.get("server_name", "")
            url = source.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            sources.append(source)

    return sources


def make_budgeted_search_fn(
    search_fn: SearchFn,
    budget_manager: BudgetManager | None,
    *,
    agent_name: str,
) -> SearchFn:
    """把 search_fn 包一层预算闸门。

    【正经注释】每次调用前查 budget_manager.can_use('search')：超预算则直接返回 []，
    并通过 record_degradation 在 governance 上标记降级，保证审计可见；未超则 record 后放行。
    budget_manager 为 None 时（兼容旧调用/无治理态）退化为透传。

    【大白话注释】给搜索函数装个"用量计数器 + 闸门"——没超额度就放行并 +1，
    超了就立刻返回空结果、并在治理日志里记一笔降级，省得搜索把预算烧光。
    """

    async def wrapped(query: str, max_results: int) -> list[dict[str, Any]]:
        """带「策略检查 + 预算闸门」的搜索包装函数。

        【正经注释】
        在透传给真正的 search_fn 之前，依次做两道前置校验：
        1) assert_tool_allowed：依据 agent_name 校验当前 agent 是否被策略允许
           调用 search 工具（工具黑白名单 / 权限治理）。不被允许则记 policy
           事件并原样抛出 PolicyViolation（硬拦截，交由上层处理）；
        2) budget_manager.can_use("search")：查询剩余搜索预算，超限则记一笔
           record_degradation（软降级，审计可见）并返回空列表 []，不中断流程。
        两关都过才 record 消费一次、再真正调用检索函数。
        budget_manager 为 None 时整个闸门跳过、直接透传，兼容无治理的旧调用路径。

        【大白话注释】
        这个函数就是给「搜索」加了个安检口，真正去搜之前先过两道关：
        - 第一关（策略）：这个 agent 配不配用搜索工具？不配就在治理日志记一笔
          「被策略拦了」，然后直接把错误抛上去（硬拦，不搜了）；
        - 第二关（预算）：搜索额度还有没有？烧光了就记一笔「降级了」，
          然后返回空列表（软拦，假装搜了个空，后面的流程还能继续跑）。
        两关都过了，才在账本上记「搜了一次」，真正去搜。
        如果根本没装预算管理器（budget_manager 是 None），那就啥都不查，直接搜。
        """
        if budget_manager is not None:
            # 【正经注释】第一关：策略权限校验。断言当前 agent 是否被允许调用 search 工具。
            # 【大白话注释】先问一句：这个 agent 有没有资格用搜索工具？
            try:
                assert_tool_allowed(agent_name, "search")
            except PolicyViolation as exc:
                # 【正经注释】策略禁止：在治理事件流记一笔 policy 拦截（policy_blocked=True），再原样向上抛异常（硬拦截）。
                # 【大白话注释】不让搜——在治理日志写一笔「被策略拦了」，然后把错误抛出去，上层自己看着办。
                record_event(
                    budget_manager.governance,
                    kind="policy",
                    agent=agent_name,
                    detail=str(exc),
                    policy_blocked=True,
                )
                raise
            # 【正经注释】第二关：预算校验。can_use 返回 False 表示 search 预算已耗尽。
            # 【大白话注释】再查一句：搜索额度还有没有？没钱了就走下面的降级。
            if not budget_manager.can_use("search"):
                # 【正经注释】软降级：记一笔降级事件（审计可见），返回空列表而非抛异常，保证流程不中断。
                # 【大白话注释】额度烧光了——记一笔「降级了」，然后返回个空列表（假装搜了个寂寞），不报错，让后面流程还能跑。
                budget_manager.record_degradation("SearchFn", "search budget exceeded")
                return []
            # 【正经注释】两关通过：消费一次 search 预算，用量计数 +1。
            # 【大白话注释】过关了——在预算账本上记一笔「搜了一次」。
            budget_manager.record("search")
        # 【正经注释】无治理（budget_manager 为 None）或两关全部通过，透传给真正的检索函数并 await 结果。
        # 【大白话注释】该查的都查完了，现在才真正去搜，把搜到的结果原样返回。
        return await search_fn(query, max_results)

    # 【正经注释】返回包装后的协程函数；调用方拿到的是这个带闸门的版本，原 search_fn 被它包在内层。
    # 【大白话注释】把这个「安检过的搜索函数」交出去——以后谁用它，都会自动先过那两道关。
    return wrapped
