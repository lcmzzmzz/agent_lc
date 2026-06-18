"""
Apify 检索源（可选）：用 Apify 抓真实 Amazon 评论/产品，作为 Tavily 之外的数据源。

【正经注释】
实现一个符合 SearchFn 签名的异步检索函数，底层通过 Apify REST API
(run-sync-get-dataset-items) 同步运行指定 actor 并取回数据集，映射为统一的
{title, href, body} 结构（与 Tavily 结果一致，供 normalize_source 处理）。
token / actor 从环境变量读取；token 缺失时工厂函数抛清晰错误，便于启动期发现。

【大白话注释】
Tavily 搜到的是网页摘要，不是真实 Amazon 评论。这个模块让你能换成 Apify，
直接抓 Amazon 真实评论/产品数据。需要 Apify 账号的 API token。
不同 actor 字段不一样，_map_item 按常见 Amazon 评论 actor 做了映射，
换 actor 时可能要调 _map_item。

【启用方式】见 docs/ecommerce-apify-setup.md
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import requests  # 项目已依赖 requests

from multi_agents.ecommerce.tools.product_search import SearchFn

logger = logging.getLogger("multi_agents.ecommerce")

# 默认 actor：Amazon 评论抓取（示例）。不同 actor 的 input/output 字段不同，
# 如果结果映射不对，请到 Apify Store 确认该 actor 的字段，调整下方 _map_item 与 payload。
DEFAULT_REVIEW_ACTOR = "compass/listing-amazon-reviews"
_APIFY_RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def _map_item(raw: dict[str, Any]) -> dict[str, str]:
    """把 Apify 返回的单条数据映射成统一 {title, href, body}。

    不同 Amazon 评论 actor 字段名可能不同（title/reviewTitle、url/reviewUrl、
    content/reviewText…），这里取一组常见字段的兜底。
    """
    return {
        "title": (
            raw.get("title")
            or raw.get("reviewTitle")
            or raw.get("productName")
            or raw.get("name")
            or "Amazon item"
        ),
        "href": (
            raw.get("url")
            or raw.get("reviewUrl")
            or raw.get("productUrl")
            or raw.get("link")
            or ""
        ),
        "body": (
            raw.get("content")
            or raw.get("reviewText")
            or raw.get("description")
            or raw.get("text")
            or raw.get("body")
            or ""
        ),
    }


def make_apify_search_fn() -> SearchFn:
    """构造一个 Apify SearchFn。token 缺失时抛错（启动期可见）。

    Returns:
        异步 search(query, max_results) -> list[{title, href, body}]
    """
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError(
            "APIFY_API_TOKEN 未配置：到 Apify → Settings → API tokens 复制个人 token，"
            "写入 .env 的 APIFY_API_TOKEN=..."
        )
    actor = os.environ.get("APIFY_REVIEW_ACTOR", DEFAULT_REVIEW_ACTOR)

    async def search(query: str, max_results: int) -> list[dict[str, Any]]:
        def _sync() -> list[dict[str, Any]]:
            try:
                url = _APIFY_RUN_URL.format(actor=actor)
                # actor input：以关键词搜 Amazon 评论。不同 actor 入参名可能不同
                # （keyword / searchQueries / asin / urls…），按所选 actor 文档调整。
                payload: dict[str, Any] = {
                    "keyword": query,
                    "maxResults": max_results,
                    "country": os.environ.get("APIFY_AMAZON_COUNTRY", "US"),
                }
                resp = requests.post(
                    url, json=payload, params={"token": token}, timeout=180
                )
                resp.raise_for_status()
                items = resp.json() if resp.content else []
                if not isinstance(items, list):
                    items = []
                mapped = [_map_item(it) for it in items[:max_results] if isinstance(it, dict)]
                logger.info(
                    f"[apify] query='{query}' actor={actor} 返回 {len(mapped)} 条"
                )
                return mapped
            except Exception as exc:
                logger.warning(f"[apify] 检索失败 query='{query}': {exc}")
                return []

        return await asyncio.to_thread(_sync)

    return search
