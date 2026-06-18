"""
评论抓取层（双数据源可插拔）：Apify 真实评论 + Tavily 摘要兜底。

【正经注释】
统一接口 ReviewSource.scrape(query, platforms, max_reviews) -> list[ReviewItem]。
- ApifyReviewScraper：Amazon 走「两步」——先用关键词搜产品拿 ASIN，再用 ASIN 抓评论。
  （Amazon 评论 actor 普遍只认 ASIN/URL，不支持品类词，故必须两步。）
- FallbackSearchReviewScraper：包装 Tavily search + 关键词抽取。
get_review_scraper() 工厂：有 APIFY_API_TOKEN 用 Apify，否则 Fallback。
Apify 运行时失败由 ReviewInsightAgent 捕获后切 Fallback。

【大白话注释】
评论两种来源：Apify 真实抓 + Tavily 搜网页兜底。Apify 抓 Amazon 评论分两步——
先搜出具体产品(ASIN)，再抓这些产品的评论（Amazon 评论只认具体产品，不认品类词）。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Protocol

import requests

from multi_agents.ecommerce.tools.product_search import SearchFn, build_ecommerce_queries
from multi_agents.ecommerce.tools.review_extractor import extract_review_insights

logger = logging.getLogger("multi_agents.ecommerce")

# Apify actorId 用 `~` 格式（username~name）。`/` 格式在 run-sync 端点会 404。
DEFAULT_ACTORS = {
    # 第一步：品类词 -> 产品 ASIN（已验证可用）
    "amazon_search": "igview-owner~amazon-search-scraper",
    # 第二步：ASIN -> 评论（free plan 可能抓不到，需 Apify 配置可用 proxy/actor）
    "amazon_reviews": "web_wanderer~amazon-reviews-extractor",
    # Reddit：actor 待验证，暂未实现（预留接口）
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
# 工具
# ---------------------------------------------------------------------------

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


def _map_amazon_review(raw: dict[str, Any]) -> ReviewItem:
    """把评论 actor 输出映射成 ReviewItem（按常见字段兜底）。"""
    return ReviewItem(
        platform="amazon",
        rating=_safe_float(
            raw.get("rating") or raw.get("reviewRating") or raw.get("starRating")
        ),
        review_text=str(
            raw.get("reviewText") or raw.get("text") or raw.get("body")
            or raw.get("content") or raw.get("review") or ""
        ),
        date=str(raw.get("date") or raw.get("reviewDate") or ""),
        helpful=_safe_int(raw.get("helpful") or raw.get("helpfulVotes") or raw.get("helpfulVotesCount")),
        product_url=str(raw.get("productUrl") or raw.get("url") or raw.get("reviewUrl") or ""),
        title=str(raw.get("title") or raw.get("reviewTitle") or ""),
        source_url=str(raw.get("reviewUrl") or raw.get("url") or ""),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Apify 真实评论抓取（Amazon 两步）
# ---------------------------------------------------------------------------

class ApifyReviewScraper:
    """通过 Apify 抓真实评论。MVP 实现 Amazon 两步；Reddit 预留接口。"""

    name = "apify"
    SUPPORTED_PLATFORMS = {"amazon"}

    def __init__(self, token: str, actors: dict[str, str] | None = None, country: str = "US"):
        self.token = token
        self.actors = {**DEFAULT_ACTORS, **(actors or {})}
        self.country = country

    async def scrape(
        self, query: str, platforms: list[str], max_reviews: int
    ) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        if "amazon" in platforms:
            items.extend(await self._scrape_amazon(query, max_reviews))
        for p in platforms:
            if p not in self.SUPPORTED_PLATFORMS:
                logger.warning(
                    f"[apify:{p}] 暂未实现（actor 待验证），跳过；该平台评论将缺失"
                )
        return items[:max_reviews]

    async def _scrape_amazon(self, query: str, max_reviews: int) -> list[ReviewItem]:
        """Amazon 两步：keyword -> ASINs -> reviews。"""
        # Step 1: 品类词 -> 产品 ASIN
        asins = await self._search_asins(query, limit=8)
        if not asins:
            logger.warning(f"[apify:amazon] 第一步 search 未拿到任何 ASIN，无法抓评论")
            return []
        logger.info(f"[apify:amazon] 第一步 search 拿到 ASIN: {asins[:5]}")
        # Step 2: ASIN -> 评论
        reviews = await self._fetch_reviews(asins[:5], max_reviews)
        reviews = [r for r in reviews if r.review_text]
        logger.info(
            f"[apify:amazon] 第二步 reviews 抓取到 {len(reviews)} 条评论"
            + ("" if reviews else "（可能需 Apify 配置付费 proxy/可用 actor 才能抓到 Amazon 评论）")
        )
        return reviews

    async def _search_asins(self, query: str, limit: int = 8) -> list[str]:
        actor = self.actors.get("amazon_search")
        if not actor:
            return []

        def _sync() -> list[str]:
            try:
                resp = requests.post(
                    _APIFY_RUN_URL.format(actor=actor),
                    json={"keyword": query, "maxResults": limit},
                    params={"token": self.token},
                    timeout=120,
                )
                resp.raise_for_status()
                rows = resp.json() if resp.content else []
                if not isinstance(rows, list):
                    return []
                return [r.get("asin") for r in rows if isinstance(r, dict) and r.get("asin")]
            except Exception as exc:
                logger.warning(f"[apify:amazon-search] 失败: {exc}")
                return []

        return await asyncio.to_thread(_sync)

    async def _fetch_reviews(self, asins: list[str], max_reviews: int) -> list[ReviewItem]:
        actor = self.actors.get("amazon_reviews")
        if not actor or not asins:
            return []

        def _sync() -> list[ReviewItem]:
            try:
                resp = requests.post(
                    _APIFY_RUN_URL.format(actor=actor),
                    json={"products": asins, "maxReviews": max_reviews},
                    params={"token": self.token},
                    timeout=180,
                )
                resp.raise_for_status()
                rows = resp.json() if resp.content else []
                if not isinstance(rows, list):
                    return []
                return [_map_amazon_review(r) for r in rows if isinstance(r, dict)]
            except Exception as exc:
                logger.warning(f"[apify:amazon-reviews] 失败: {exc}")
                return []

        return await asyncio.to_thread(_sync)


# ---------------------------------------------------------------------------
# Tavily 摘要兜底
# ---------------------------------------------------------------------------

class FallbackSearchReviewScraper:
    """无 Apify token / Apify 失败时的兜底：Tavily 搜含评论的网页，抽取评论句。

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
        from multi_agents.ecommerce.tools.product_search import search_sources

        sources = await search_sources(
            queries=queries, search_fn=self.search_fn, max_results_per_query=3
        )
        sentences = extract_review_insights(sources, limit=max_reviews)
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
        logger.info(f"[fallback] query='{query}' Tavily 抽取评论句 {len(items)} 条")
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
        actors: dict[str, str] = {}
        env_map = {
            "APIFY_AMAZON_SEARCH_ACTOR": "amazon_search",
            "APIFY_AMAZON_REVIEWS_ACTOR": "amazon_reviews",
        }
        for env_key, actor_key in env_map.items():
            v = os.environ.get(env_key)
            if v:
                actors[actor_key] = v
        country = os.environ.get("APIFY_AMAZON_COUNTRY", "US")
        return ApifyReviewScraper(token, actors=actors, country=country), None

    if search_fn is None:
        from multi_agents.ecommerce.runner import default_search_fn

        search_fn = default_search_fn
    return (
        FallbackSearchReviewScraper(search_fn),
        "no APIFY_API_TOKEN, using Tavily fallback",
    )
