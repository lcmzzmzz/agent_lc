"""
评论抓取层（双数据源可插拔）：Apify 真实评论 + Tavily 摘要兜底。

【正经注释】
定义统一接口 ReviewSource.scrape(query, platforms, max_reviews) -> list[ReviewItem]，
内含两个实现：
- ApifyReviewScraper：通过 Apify 调平台 actor 抓真实评论（Amazon / Reddit），返回结构化
  ReviewItem（rating / review_text / date / helpful / product_url）。
- FallbackSearchReviewScraper：包装现有 Tavily search + 关键词抽取，把网页里的评论句
  包成 ReviewItem（platform=web）。
get_review_scraper() 工厂：有 APIFY_API_TOKEN 用 Apify，否则用 Fallback，保证无 token 时
demo 仍可跑。Apify 运行时失败由 ReviewInsightAgent 捕获后切 Fallback。

【大白话注释】
评论有两个来源：Apify 直接抓 Amazon/Reddit 真实评论，Tavily 搜含评论的网页兜底。
这个模块把两种来源统一成同一个"取评论"接口，谁能用就用谁，都没了就降级。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Protocol

import requests

from multi_agents.ecommerce.tools.product_search import SearchFn, build_ecommerce_queries
from multi_agents.ecommerce.tools.review_extractor import extract_review_insights
from multi_agents.ecommerce.tools.source_normalizer import normalize_source

logger = logging.getLogger("multi_agents.ecommerce")

# 各平台默认 Apify actor（可在 .env 用 APIFY_AMAZON_ACTOR / APIFY_REDDIT_ACTOR 覆盖）
DEFAULT_ACTORS = {
    "amazon": "compass/listing-amazon-reviews",
    "reddit": "trudax/reddit-scraper",
}
_APIFY_RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


class ReviewItem(dict):
    """一条评论/反馈。dict 子类便于序列化，字段可选。

    platform: amazon | reddit | web
    rating:   1-5（Amazon 有，Reddit/web 通常无）
    review_text / date / helpful / product_url / title / source_url / raw
    """

    @property
    def platform(self) -> str:
        return self.get("platform", "web")

    @property
    def review_text(self) -> str:
        return self.get("review_text", "")


class ReviewSource(Protocol):
    """评论源统一接口。"""

    name: str

    async def scrape(
        self, query: str, platforms: list[str], max_reviews: int
    ) -> list[ReviewItem]:  # pragma: no cover - 接口定义
        ...


# ---------------------------------------------------------------------------
# 字段映射：不同平台/actor 输出字段不同，这里按常见字段兜底
# ---------------------------------------------------------------------------

def _map_amazon(raw: dict[str, Any]) -> ReviewItem:
    return ReviewItem(
        platform="amazon",
        rating=_safe_float(raw.get("rating") or raw.get("stars")),
        review_text=str(
            raw.get("reviewText") or raw.get("content") or raw.get("text") or raw.get("body") or ""
        ),
        date=str(raw.get("date") or raw.get("reviewDate") or ""),
        helpful=_safe_int(raw.get("helpful") or raw.get("helpfulVotes")),
        product_url=str(raw.get("productUrl") or raw.get("url") or raw.get("reviewUrl") or ""),
        title=str(raw.get("title") or raw.get("productName") or ""),
        source_url=str(raw.get("url") or raw.get("reviewUrl") or ""),
        raw=raw,
    )


def _map_reddit(raw: dict[str, Any]) -> ReviewItem:
    return ReviewItem(
        platform="reddit",
        rating=None,
        review_text=str(
            raw.get("body") or raw.get("text") or raw.get("selftext") or raw.get("content") or ""
        ),
        date=str(raw.get("createdAt") or raw.get("createdUtc") or raw.get("date") or ""),
        helpful=_safe_int(raw.get("upVotes") or raw.get("score") or raw.get("upvotes")),
        product_url=str(raw.get("url") or raw.get("permalink") or raw.get("link") or ""),
        title=str(raw.get("title") or ""),
        source_url=str(raw.get("url") or raw.get("permalink") or ""),
        raw=raw,
    )


_PLATFORM_MAPPER = {"amazon": _map_amazon, "reddit": _map_reddit}


def _safe_float(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int:
    try:
        return int(v) if v not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Apify 真实评论抓取
# ---------------------------------------------------------------------------

class ApifyReviewScraper:
    """通过 Apify 抓各平台真实评论。MVP 支持 amazon / reddit。"""

    name = "apify"

    def __init__(self, token: str, actors: dict[str, str] | None = None, country: str = "US"):
        self.token = token
        self.actors = {**DEFAULT_ACTORS, **(actors or {})}
        self.country = country

    async def scrape(
        self, query: str, platforms: list[str], max_reviews: int
    ) -> list[ReviewItem]:
        per_platform = max(3, max_reviews // max(1, len(platforms)))
        tasks = [
            self._scrape_platform(p, query, per_platform)
            for p in platforms
            if p in self.actors
        ]
        results = await asyncio.gather(*tasks)
        items: list[ReviewItem] = []
        for batch in results:
            items.extend(batch)
        return items[:max_reviews]

    async def _scrape_platform(
        self, platform: str, query: str, max_results: int
    ) -> list[ReviewItem]:
        actor = self.actors[platform]
        mapper = _PLATFORM_MAPPER[platform]

        def _sync() -> list[ReviewItem]:
            try:
                url = _APIFY_RUN_URL.format(actor=actor)
                payload: dict[str, Any] = {
                    "keyword": query,
                    "searchQueries": [query],
                    "maxResults": max_results,
                    "startUrls": [],
                }
                if platform == "amazon":
                    payload["country"] = self.country
                resp = requests.post(
                    url, json=payload, params={"token": self.token}, timeout=180
                )
                resp.raise_for_status()
                rows = resp.json() if resp.content else []
                if not isinstance(rows, list):
                    rows = []
                mapped = [mapper(r) for r in rows if isinstance(r, dict)]
                mapped = [m for m in mapped if m.review_text]  # 过滤无正文
                logger.info(
                    f"[apify:{platform}] query='{query}' actor={actor} 返回 {len(mapped)} 条评论"
                )
                return mapped
            except Exception as exc:
                logger.warning(f"[apify:{platform}] 抓取失败 query='{query}': {exc}")
                return []

        return await asyncio.to_thread(_sync)


# ---------------------------------------------------------------------------
# Tavily 摘要兜底
# ---------------------------------------------------------------------------

class FallbackSearchReviewScraper:
    """无 Apify token 时的兜底：用 Tavily 搜含评论的网页，抽取评论句。

    review_text = 抽取的抱怨句；platform=web；rating=None；source_url=网页 url。
    """

    name = "web_fallback"

    def __init__(self, search_fn: SearchFn, max_queries: int = 4):
        self.search_fn = search_fn
        self.max_queries = max_queries

    async def scrape(
        self, query: str, platforms: list[str], max_reviews: int
    ) -> list[ReviewItem]:
        queries = build_ecommerce_queries(
            query=query, target_market="US", intent="review", max_queries=self.max_queries
        )
        # 复用 search_sources 的去重/标准化
        from multi_agents.ecommerce.tools.product_search import search_sources

        sources = await search_sources(
            queries=queries, search_fn=self.search_fn, max_results_per_query=3
        )
        sentences = extract_review_insights(sources, limit=max_reviews)
        # url 索引便于回填 source_url
        url_by_idx = [s.get("url", "") for s in sources]
        items: list[ReviewItem] = []
        for i, sentence in enumerate(sentences):
            items.append(
                ReviewItem(
                    platform="web",
                    rating=None,
                    review_text=sentence,
                    date="",
                    helpful=0,
                    product_url="",
                    title="",
                    source_url=url_by_idx[min(i, len(url_by_idx) - 1)] if url_by_idx else "",
                    raw={"from": "tavily_fallback"},
                )
            )
        logger.info(
            f"[fallback] query='{query}' Tavily 抽取评论句 {len(items)} 条"
        )
        return items


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------

def get_review_scraper(
    search_fn: SearchFn | None = None,
) -> tuple[ReviewSource, str | None]:
    """选择当前可用的评论源。

    Returns:
        (scraper, fallback_reason)。fallback_reason 为 None 表示用了 Apify 真实评论；
        非 None 表示走了 Tavily 兜底（含原因）。
    """
    token = os.environ.get("APIFY_API_TOKEN")
    if token:
        actors = {}
        if os.environ.get("APIFY_AMAZON_ACTOR"):
            actors["amazon"] = os.environ["APIFY_AMAZON_ACTOR"]
        if os.environ.get("APIFY_REDDIT_ACTOR"):
            actors["reddit"] = os.environ["APIFY_REDDIT_ACTOR"]
        country = os.environ.get("APIFY_AMAZON_COUNTRY", "US")
        return ApifyReviewScraper(token, actors=actors, country=country), None

    if search_fn is None:
        from multi_agents.ecommerce.runner import default_search_fn

        search_fn = default_search_fn
    return (
        FallbackSearchReviewScraper(search_fn),
        "no APIFY_API_TOKEN, using Tavily fallback",
    )
