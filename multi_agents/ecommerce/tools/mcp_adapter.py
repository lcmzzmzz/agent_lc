"""Optional MCP evidence adapter for ecommerce search.

【正经注释】
MCP（Model Context Protocol）证据适配器：在不破坏默认检索链路的前提下，
把 MCP 工具返回的结果「叠加」到 base search_fn 结果之后，归一化成与
Tavily/DuckDuckGo 一致的 EcommerceSource 形状。MCP 是可选能力——
mcp_enabled=False 或无 mcp_configs 时直接走 base；任何 MCP 异常都被
捕获并降级为「仅返回 base 结果」，保证 MCP 故障永不阻塞主检索链路。

【大白话注释】
这是个「选配」的 MCP 搜索外挂：默认走原本的搜索，开了 MCP 之后，
会在原搜索结果后面再追加一批 MCP 找到的证据。整理成统一格式，方便后面 Agent 用。
MCP 出任何错（连不上、报异常）都不影响原本的搜索，照常用 base 结果交差，
只是会在治理日志里记一笔「失败了」。总结：MCP 是锦上添花，不是雪中送炭。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from multi_agents.ecommerce.runtime.policy_guard import redact_secrets
from multi_agents.ecommerce.runtime.telemetry import increment_usage, record_event
from multi_agents.ecommerce.tools.product_search import SearchFn

# MCP 检索函数签名：(query, max_results, mcp_configs, mcp_strategy) -> list[原始结果dict]
# 前 2 个参数与 SearchFn 一致（便于未来直接复用），后 2 个是 MCP 专属配置与策略。
McpSearchFn = Callable[
    [str, int, list[dict[str, Any]], str],
    Awaitable[list[dict[str, Any]]],
]


def normalize_mcp_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    """把一条 MCP 原始结果归一化成 EcommerceSource 兼容形状。

    【正经注释】
    MCP 工具返回的字段名不统一（url vs href、content vs body vs snippet），
    这里按优先级兜底链选值，并强制打上 source_type="mcp"，
    同时保留 tool_name / server_name 两个溯源字段，让后续 Agent 能区分
    「这条证据来自 MCP 哪个工具 / 哪个 server」。返回的 dict 不带 url/snippet 键，
    而是用 href/body——和 product_search.normalize_source 的输入形状对齐，
    保证后面再走一次 normalize_source 时不会被丢字段。

    【大白话注释】
    MCP 返回的结果长得乱七八糟（有的叫 url，有的叫 href），这里统一改成：
    - title：标题
    - href：链接
    - body：内容
    - source_type：固定 "mcp"（标注「这条来自 MCP」）
    - tool_name / server_name：是哪个 MCP 工具/服务给的，方便事后溯源
    """
    return {
        "title": str(raw.get("title") or raw.get("name") or "MCP result"),
        "href": str(raw.get("href") or raw.get("url") or ""),
        "body": str(raw.get("body") or raw.get("content") or raw.get("snippet") or ""),
        "source_type": "mcp",
        "tool_name": str(raw.get("tool_name") or raw.get("tool") or ""),
        "server_name": str(raw.get("server_name") or raw.get("server") or ""),
    }


async def _empty_mcp_search(
    query: str,
    max_results: int,
    mcp_configs: list[dict[str, Any]],
    mcp_strategy: str,
) -> list[dict[str, Any]]:
    """MCP 检索的默认空实现：未注入真实 MCP 客户端时返回空，等价于「没有 MCP 证据」。

    【正经注释】
    保留这个空实现是为了：调用方没传 mcp_search_fn 时，make_mcp_augmented_search_fn
    仍然能正常工作（不抛错、不算失败、只是不追加任何 MCP 结果）。
    真实 MCP 客户端接线后，调用方注入一个真的 mcp_search_fn 即可覆盖默认行为。

    【大白话注释】
    默认情况下 MCP 「啥也搜不到」——不算出错，就是没结果。等以后真接上 MCP 服务了，
    再把真的搜索函数传进来顶替它。
    """
    return []


def _server_names(configs: list[dict[str, Any]]) -> list[str]:
    return [str(redact_secrets(c.get("name", "mcp"))) for c in configs]


def _redacted_error(exc: Exception) -> str:
    redacted = redact_secrets({"error": str(exc)})
    return str(redacted.get("error", ""))


def _result_key(row: Mapping[str, Any]) -> str:
    href = str(row.get("href") or row.get("url") or "").strip()
    if href:
        return f"href:{href}"
    return f"title:{row.get('title', '')}|body:{row.get('body') or row.get('content') or ''}"


def _merge_base_and_mcp_results(
    base_results: list[dict[str, Any]],
    mcp_results: list[dict[str, Any]],
    max_results: int,
) -> list[dict[str, Any]]:
    limit = max(0, int(max_results))
    if limit == 0:
        return []
    if not mcp_results:
        return base_results[:limit]

    seen = {_result_key(row) for row in base_results if _result_key(row)}
    unique_mcp: list[dict[str, Any]] = []
    for row in mcp_results:
        key = _result_key(row)
        if key in seen:
            continue
        seen.add(key)
        unique_mcp.append(row)

    if not unique_mcp:
        return base_results[:limit]
    if len(base_results) + len(unique_mcp) <= limit:
        return [*base_results, *unique_mcp]

    reserved_mcp_slots = min(len(unique_mcp), max(1, limit // 3))
    selected_base = base_results[: max(0, limit - reserved_mcp_slots)]
    remaining_slots = max(0, limit - len(selected_base))
    return [*selected_base, *unique_mcp[:remaining_slots]]


def make_mcp_augmented_search_fn(
    base_search_fn: SearchFn,
    *,
    mcp_enabled: bool,
    mcp_configs: list[dict[str, Any]] | None,
    mcp_strategy: str,
    governance: dict[str, Any],
    mcp_context: dict[str, Any],
    mcp_search_fn: McpSearchFn | None = None,
) -> SearchFn:
    """把 base search_fn 包一层 MCP 增强：base 结果在前，MCP 归一化结果在后。

    【正经注释】
    返回一个新的 SearchFn。每次调用时：
    1) 先 await base_search_fn 拿基础结果；
    2) 若 mcp_enabled=False 或 configs 为空 → 直接返回 base（不记账、不抛错）；
    3) 否则先 increment_usage('external_api_call_count') 记一笔外部调用，
       再 await mcp_search_fn，归一化后按 max_results 上限追加到 base 之后；
       成功则记一条 kind="tool" 治理事件 + mcp_context.tool_calls 一条 success 记录；
    4) MCP 抛异常 → 记 kind="failure" 事件 + 一条 failed tool_calls 记录，
       只返回 base 结果（MCP 故障永不阻塞主链路）。

    mcp_context 在这里被「原地修改」（与 governance 一样全程共享同一引用），
    enabled/strategy/tool_calls 字段由本函数维护。

    【大白话注释】
    给原来的搜索函数装个「MCP 外挂」，返回一个新的搜索函数。每次搜的时候：
    - 先用原来的搜索拿一批基础结果；
    - 如果 MCP 没开、或者没配 MCP 服务器，就直接交回基础结果（啥也不干）；
    - 如果开了 MCP：先在账本上记「调了一次外部 API」，再去 MCP 搜一批，
      整理好接在基础结果后面（超过 max_results 就截断），并在治理日志记一笔成功；
    - MCP 出任何错：不抛异常，只在治理日志记一笔失败、把原因写进 mcp_context，
      然后照常交回基础结果。一句话：MCP 挂了不影响原本的搜索。
    """
    configs = mcp_configs or []
    # 把本次 MCP 开关 / 策略刷进 mcp_context（全程共享同一 dict，evaluation_summary 也会读它）
    mcp_context["enabled"] = bool(mcp_enabled)
    mcp_context["strategy"] = mcp_strategy
    mcp_context["config_count"] = len(configs)
    mcp_context["servers"] = _server_names(configs)
    mcp_context.setdefault("tool_calls", [])
    # 没注入真实 MCP 客户端 → 用空实现兜底（不抛错、不算失败，只是不追加结果）
    selected_mcp_search = mcp_search_fn or _empty_mcp_search

    async def search(query: str, max_results: int) -> list[dict[str, Any]]:
        """带 MCP 增强的搜索：base 在前、MCP 归一化结果在后，MCP 失败则降级为 base-only。"""
        # ① 先拿基础结果（base 永远先跑，不受 MCP 开关影响）
        base_results = await base_search_fn(query, max_results)
        # ② MCP 未启用或没配 server → 直接返回 base（不进 try、不记账）
        if not mcp_enabled or not configs:
            return base_results
        try:
            # ③ MCP 调用前先记账：external_api_call_count +1（无论成败，这是一次真实外部调用）
            increment_usage(governance, "external_api_call_count", 1)
            raw_results = await selected_mcp_search(
                query,
                max_results,
                configs,
                mcp_strategy,
            )
            # ④ 逐条归一化成 EcommerceSource 兼容形状（带 source_type="mcp" + tool/server 溯源）
            normalized = [normalize_mcp_result(row) for row in raw_results]
            # ⑤ 在 mcp_context 追加一条成功 tool_call 记录（server/tool/query/status/result_count）
            mcp_context["tool_calls"].append(
                {
                    "server": ",".join(_server_names(configs)),
                    "server_names": _server_names(configs),
                    "tool": "search",
                    "query": query,
                    "status": "success",
                    "result_count": len(normalized),
                }
            )
            # ⑥ 治理事件流记一笔 kind="tool"（审计可见「MCP 被用过、返回了多少条」）
            record_event(
                governance,
                kind="tool",
                agent="MCPSearchAdapter",
                detail=f"mcp search returned {len(normalized)} results",
            )
            # ⑦ 合并 base + MCP，按 max_results 上限截断（避免 MCP 把结果灌爆）
            return _merge_base_and_mcp_results(base_results, normalized, max_results)
        except Exception as exc:
            # ⑧ MCP 任何异常都不抛到外面：记 failed tool_call + failure 事件，只返回 base
            #    ★ 这是「MCP 故障不阻塞主链路」的关键降级分支
            mcp_context["tool_calls"].append(
                {
                    "server": ",".join(_server_names(configs)),
                    "server_names": _server_names(configs),
                    "tool": "search",
                    "query": query,
                    "status": "failed",
                    "result_count": 0,
                    "error": _redacted_error(exc),
                }
            )
            record_event(
                governance,
                kind="failure",
                agent="MCPSearchAdapter",
                detail="mcp search failed",
                error_type=exc.__class__.__name__,
                error_message=_redacted_error(exc),
            )
            return base_results

    return search
