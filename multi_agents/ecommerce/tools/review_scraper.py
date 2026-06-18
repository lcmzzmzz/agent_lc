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
import re
from typing import Any, Protocol

import requests

from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
from multi_agents.ecommerce.tools.product_search import SearchFn, build_ecommerce_queries
from multi_agents.ecommerce.tools.review_extractor import extract_review_insights_with_source

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
        self, query: str, platforms: list[str], max_reviews: int,
        *, search_keyword: str | None = None,
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


# ---------------------------------------------------------------------------
# 产品相关性校验
# ---------------------------------------------------------------------------
# 这些是「修饰词」而非品类核心词：bluetooth/wireless/portable 这种词几乎出现在
# 任何电子产品的标题里（手机也带 bluetooth），拿它们判相关性会把「搜音箱返回手机」
# 这种跑偏误判为相关。过滤掉，留下真正的品类词（speaker/blender/feeder…）。
_GENERIC_MODIFIERS = {
    "bluetooth", "wireless", "portable", "mini", "smart", "usb", "type",
    "rechargeable", "electric", "digital", "best", "top", "cheap", "new",
    "for", "the", "and", "with", "of",
}


def _category_terms(keyword: str) -> list[str]:
    """从（英文）搜索关键词里抽出品类核心词：去修饰词 + 去短词。

    例：'bluetooth speaker' -> ['speaker']；'portable blender' -> ['blender']；
    'automatic pet feeder' -> ['automatic'（>2 字母保留）, 'pet', 'feeder']。
    keyword 为空/纯中文（re.findall 取不到）时返回 []。
    """
    toks = re.findall(r"[a-z0-9]+", (keyword or "").lower())
    cats = [t for t in toks if t not in _GENERIC_MODIFIERS and len(t) > 2]
    return cats or toks


def _filter_relevant_products(
    products: list[dict], keyword: str, min_relevant: int = 1
) -> list[dict]:
    """校验 search 返回的产品是否与 keyword 真相关，不相关则返回空（触发降级）。

    【正经注释】
    Apify free actor 偶发会对中文/异常 keyword 返回默认热门商品（如搜「蓝牙音箱」
    返回一堆三星手机 ASIN）。若不拦截，后续评论会全程建立在错误产品上。
    这里要求产品 title 至少包含 keyword 的一个品类核心词；相关产品数 < min_relevant
    即判定 search 跑偏，返回 []，由 ReviewInsightAgent 自动降级 Tavily。

    【大白话注释】
    搜音箱却返回手机，就别用这些手机去抓评论了——直接退回 Tavily 兜底，总比给错答案强。
    """
    cats = _category_terms(keyword)
    relevant: list[dict] = []
    for p in products:
        title = (p.get("title") or "").lower()
        if not title:
            continue
        if cats and any(c in title for c in cats):
            relevant.append(p)
    if len(relevant) < min_relevant:
        sample = ", ".join((p.get("title") or "")[:50] for p in products[:3])
        logger.info(
            f"[apify:relevance] 相关性校验失败：keyword={keyword!r} cats={cats} "
            f"相关产品数={len(relevant)}<{min_relevant}，返回产品如[{sample}]，将降级"
        )
        return []
    return relevant


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

    def __init__(
        self,
        token: str,
        actors: dict[str, str] | None = None,
        country: str = "US",
        governance: dict[str, Any] | None = None,
        budget_manager: BudgetManager | None = None,
    ):
        self.token = token
        self.actors = {**DEFAULT_ACTORS, **(actors or {})}
        self.country = country
        self.governance = governance
        self.budget_manager = budget_manager

    def _can_call_external_api(self, operation: str) -> bool:
        if self.budget_manager is None:
            return True
        if self.budget_manager.can_use("external_api"):
            self.budget_manager.record("external_api")
            return True
        self.budget_manager.record_blocked(
            "ApifyReviewScraper",
            f"external api budget exceeded before {operation}",
        )
        logger.warning(f"[apify:{operation}] external_api 预算耗尽，跳过请求")
        return False

    async def scrape(
        self, query: str, platforms: list[str], max_reviews: int,
        *, search_keyword: str | None = None,
    ) -> list[ReviewItem]:
        items: list[ReviewItem] = []
        if "amazon" in platforms:
            # search_keyword（英文，由 ReviewInsightAgent 翻译）命中率高、且可用于相关性校验；
            # 未提供则退回 query 原文。
            items.extend(await self._scrape_amazon(search_keyword or query, max_reviews))
        for p in platforms:
            if p not in self.SUPPORTED_PLATFORMS:
                logger.warning(
                    f"[apify:{p}] 暂未实现（actor 待验证），跳过；该平台评论将缺失"
                )
        return items[:max_reviews]

    async def _scrape_amazon(self, keyword: str, max_reviews: int) -> list[ReviewItem]:
        """Amazon 两步：keyword -> 相关产品 ASIN -> reviews。

        关键：第一步 search 后做相关性校验。Apify free actor 偶发会对异常/中文 keyword
        返回默认热门商品（如搜音箱返回手机），若不拦截评论会全程跑偏。校验不过则返回 []，
        由 ReviewInsightAgent 自动降级 Tavily。
        """
        # Step 1: keyword -> 产品列表（含 title，用于相关性校验）
        products = await self._search_products(keyword, limit=8)
        if not products:
            logger.warning(f"[apify:amazon] 第一步 search 未拿到任何产品，无法抓评论")
            return []
        # 相关性校验：挡掉「搜音箱返回手机」这类跑偏
        relevant = _filter_relevant_products(products, keyword)
        if not relevant:
            logger.warning("[apify:amazon] 相关性校验未通过，返回空 → 上层降级 Tavily")
            return []
        asins = [p["asin"] for p in relevant]
        logger.info(
            f"[apify:amazon] 第一步 search 拿到 {len(relevant)} 个相关产品: "
            f"{[(p['asin'], p['title'][:40]) for p in relevant[:5]]}"
        )
        # Step 2: ASIN -> 评论
        reviews = await self._fetch_reviews(asins[:5], max_reviews)
        reviews = [r for r in reviews if r.review_text]
        logger.info(
            f"[apify:amazon] 第二步 reviews 抓取到 {len(reviews)} 条评论"
            + ("" if reviews else "（可能需 Apify 配置付费 proxy/可用 actor 才能抓到 Amazon 评论）")
        )
        return reviews

    async def _search_products(self, keyword: str, limit: int = 8) -> list[dict]:
        """第一步：keyword -> 产品列表 [{asin, title}]。title 用于相关性校验。"""
        actor = self.actors.get("amazon_search")
        if not actor:
            return []

        def _sync() -> list[dict]:
            try:
                if not self._can_call_external_api("amazon-search"):
                    return []
                resp = requests.post(
                    _APIFY_RUN_URL.format(actor=actor),
                    json={
                        # actor 实际 input schema（见 Apify store 文档）：
                        #   query ✅ Required（不是 keyword）、maxPages（不是 maxResults）、country
                        # 旧代码传 keyword/maxResults → actor 不认 → 退化成默认搜索 "Smart Phone"
                        # —— 这才是「搜蓝牙音箱返回三星手机」的真因（不是中文 keyword 问题）。
                        "query": keyword,
                        "maxPages": 1,        # 1 页 ≈ 10-16 产品，足够 limit 截断
                        "country": self.country,
                    },
                    params={"token": self.token},
                    timeout=120,
                )
                resp.raise_for_status()
                rows = resp.json() if resp.content else []
                if not isinstance(rows, list):
                    return []
                products = []
                for r in rows:
                    if not isinstance(r, dict) or not r.get("asin"):
                        continue
                    # title 字段：actor 实际叫 product_title（不是 title/name/productName）。
                    # 旧代码三个兜底名全 miss → title 恒空 → 相关性校验全 skip → 误降级。
                    # product_title 优先，title/name 兜底（兼容旧测试 mock）。
                    # 顺带捕获的丰富字段供后续竞品/选品分析（销量/评分/badge 是 Amazon 金矿）。
                    products.append({
                        "asin": r.get("asin"),
                        "title": str(
                            r.get("product_title") or r.get("title") or r.get("name") or ""
                        ),
                        "url": str(r.get("product_url") or ""),
                        "price": str(r.get("product_price") or ""),
                        "rating": _safe_float(r.get("product_star_rating")),
                        "num_ratings": _safe_int(r.get("product_num_ratings")),
                        "sales_volume": str(r.get("sales_volume") or ""),
                        "is_best_seller": bool(r.get("is_best_seller")),
                        "is_amazon_choice": bool(r.get("is_amazon_choice")),
                    })
                return products[:limit]
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
                if not self._can_call_external_api("amazon-reviews"):
                    return []
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

    def __init__(self, search_fn: SearchFn, target_market: str = "US", max_queries: int = 4):
        self.search_fn = search_fn
        self.target_market = target_market
        self.max_queries = max_queries

    async def scrape(
        self, query: str, platforms: list[str], max_reviews: int,
        *, search_keyword: str | None = None,
    ) -> list[ReviewItem]:
        queries = build_ecommerce_queries(
            query=query,
            target_market=self.target_market,
            intent="review",
            max_queries=self.max_queries,
        )
        from multi_agents.ecommerce.tools.product_search import search_sources

        sources = await search_sources(
            queries=queries, search_fn=self.search_fn, max_results_per_query=3
        )
        # 抽取 (句子, 来源 url)：每句绑定它真正来自的网页 url，不再按下标错配
        pairs = extract_review_insights_with_source(sources, limit=max_reviews)
        items: list[ReviewItem] = []
        for sentence, url in pairs:
            items.append(
                ReviewItem(
                    platform="web",
                    rating=None,
                    review_text=sentence,
                    date="",
                    helpful=0,
                    product_url="",
                    title="",
                    source_url=url,
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
    governance: dict[str, Any] | None = None,
    budget_manager: BudgetManager | None = None,
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
        return (
            ApifyReviewScraper(
                token,
                actors=actors,
                country=country,
                governance=governance,
                budget_manager=budget_manager,
            ),
            None,
        )

    if search_fn is None:
        from multi_agents.ecommerce.runner import default_search_fn

        search_fn = default_search_fn
    return (
        FallbackSearchReviewScraper(search_fn),
        "no APIFY_API_TOKEN, using Tavily fallback",
    )
