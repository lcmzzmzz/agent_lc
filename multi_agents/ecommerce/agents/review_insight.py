"""
ReviewInsightAgent：用户评论痛点洞察（双数据源：Apify 真实评论 + Tavily 兜底）。

【正经注释】
异步节点。通过 get_review_scraper() 拿到当前评论源：
- 有 APIFY_API_TOKEN → ApifyReviewScraper 抓 Amazon/Reddit 真实评论
- 无 token 或 Apify 运行时失败 → 自动降级 FallbackSearchReviewScraper（Tavily 摘要）
拿到评论后用 LLM 归纳中文痛点。audit_log 记录 review_source/review_count/platforms/
fallback_reason，便于观测评论到底来自哪、降级了没。

【大白话注释】
先试着抓真实评论（Apify）；抓不到就退回 Tavily 搜网页里的评论句。
不管哪条路，最后都让大模型把评论归纳成几条中文痛点，并在日志里记清楚评论来源。
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.llm_helper import LlmFn, llm_json, llm_text
from multi_agents.ecommerce.prompts import REVIEW_INSIGHT_SYSTEM_PROMPT
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn
from multi_agents.ecommerce.tools.review_scraper import (
    FallbackSearchReviewScraper,
    ReviewItem,
    ReviewSource,
    get_review_scraper,
)

logger = logging.getLogger(__name__)


def _review_platforms() -> list[str]:
    """评论抓取平台（Apify 用）。默认 amazon+reddit，可用 APIFY_REVIEW_PLATFORMS 覆盖。"""
    raw = os.environ.get("APIFY_REVIEW_PLATFORMS", "amazon,reddit")
    return [p.strip() for p in raw.split(",") if p.strip()] or ["amazon", "reddit"]


_KEYWORD_TRANSLATE_PROMPT = (
    "你是 Amazon 搜索关键词翻译器。把用户给出的商品查询（可能为中文）翻译成"
    "最精准的 1-4 个英文单词的 Amazon 搜索关键词。只返回关键词本身，不要解释、不要标点。"
    "示例：蓝牙音箱→bluetooth speaker；便携搅拌机→portable blender；"
    "宠物自动喂食器→automatic pet feeder；露营风扇→camping fan。"
)


async def _to_search_keyword(llm_fn: LlmFn | None, query: str) -> str:
    """把 query（可能中文）翻成英文 Amazon 搜索关键词。

    【正经注释】Apify amazon-search actor 对英文 keyword 命中率显著高于中文，且英文
    关键词可用于产品相关性校验（中文 title 没法校验）。翻译失败/无 llm_fn 时回退 query 原文。

    【大白话注释】把「蓝牙音箱」翻成 bluetooth speaker 再丢给亚马逊搜，搜得准、还能校验
    返回的到底是不是音箱。翻不了就用原词，最差也会被相关性校验挡住后降级。
    """
    text, used = await llm_text(llm_fn, _KEYWORD_TRANSLATE_PROMPT, f"查询: {query}")
    if used and text:
        kw = re.sub(r"[^\w\s-]", " ", text).strip().lower()[:60]
        if kw:
            return kw
    return query


def _collect_evidence(items: list[ReviewItem]) -> list[dict[str, Any]]:
    """从评论的 source_url/product_url 去重收集引用。"""
    seen: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for it in items:
        url = it.get("source_url") or it.get("product_url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        snippet = (it.review_text or "")[:200]
        evidence.append(
            {
                "title": it.get("title") or f"{it.platform} review",
                "url": url,
                "source_type": it.platform if it.platform in ("amazon", "reddit") else "review_site",
                "snippet": snippet,
                "content": it.review_text,
            }
        )
    return evidence


async def _summarize_pain_points_zh(
    llm_fn: LlmFn | None, texts: list[str]
) -> tuple[list[str] | None, bool]:
    """用 LLM 把评论文本归纳为中文痛点。返回 (zh_list | None, used_llm)。"""
    if not llm_fn or not texts:
        return None, False
    user = (
        "以下是从公开资料/平台抓取的用户评论与反馈（可能为英文）：\n"
        + "\n".join(f"- {t}" for t in texts[:12])
        + "\n请把它们归纳成 3-6 条中文用户痛点，每条一句话，客观描述问题。"
        '只返回 JSON：{"pain_points":["中文痛点1","中文痛点2"]}'
    )
    data, used = await llm_json(llm_fn, REVIEW_INSIGHT_SYSTEM_PROMPT, user)
    if used and isinstance(data.get("pain_points"), list) and data["pain_points"]:
        zh = [str(p) for p in data["pain_points"] if p][:6]
        if zh:
            return zh, True
    return None, False


async def run_review_insight(
    state: EcommerceResearchState,
    *,
    search_fn: SearchFn,
    llm_fn: LlmFn | None = None,
) -> EcommerceResearchState:
    started = time.perf_counter()
    config = get_depth_config(state["depth"])
    max_reviews = config["max_sources_per_agent"] * 3
    platforms = _review_platforms()

    scraper: ReviewSource
    scraper, fallback_reason = get_review_scraper(search_fn)
    search_keyword = await _to_search_keyword(llm_fn, state["query"])
    logger.info(
        f"[ReviewInsight] 开始 query='{state['query']}' keyword='{search_keyword}' "
        f"scraper={scraper.name} platforms={platforms}"
    )

    # 抓评论：Apify 失败/空/产品不相关 → 自动降级 Fallback
    items: list[ReviewItem] = []
    try:
        items = await scraper.scrape(
            state["query"], platforms, max_reviews, search_keyword=search_keyword
        )
        if not items and scraper.name == "apify":
            logger.warning("[ReviewInsight] Apify 返回 0 条评论（含相关性校验拦截），降级 Tavily fallback")
            scraper = FallbackSearchReviewScraper(
                search_fn, target_market=state.get("target_market", "US")
            )
            items = await scraper.scrape(state["query"], platforms, max_reviews)
            fallback_reason = "apify returned 0 reviews"
    except Exception as exc:
        logger.error(f"[ReviewInsight] scraper 抓取失败({scraper.name}): {exc}", exc_info=True)
        if scraper.name == "apify":
            scraper = FallbackSearchReviewScraper(
                search_fn, target_market=state.get("target_market", "US")
            )
            try:
                items = await scraper.scrape(state["query"], platforms, max_reviews)
            except Exception as exc2:
                logger.error(f"[ReviewInsight] fallback 也失败: {exc2}")
                items = []
            fallback_reason = f"apify failed: {exc}"
        else:
            fallback_reason = f"{scraper.name} failed: {exc}"

    raw_texts = [it.review_text for it in items if it.review_text]
    evidence = _collect_evidence(items)
    logger.info(
        f"[ReviewInsight] 抓取完成 source={scraper.name} review_count={len(items)} fallback_reason={fallback_reason}"
    )

    # LLM 中文归纳
    zh_pain_points, used_llm = await _summarize_pain_points_zh(llm_fn, raw_texts)
    final_pain_points = zh_pain_points or raw_texts
    if raw_texts and not used_llm and llm_fn:
        logger.warning("[ReviewInsight] LLM 中文归纳失败，保留原文")
    language = "zh" if used_llm else ("raw" if raw_texts else "none")

    state["review_result"] = {
        "summary": "基于多源评论/反馈归纳用户痛点；评论来源见 review_source 字段。",
        "pain_points": final_pain_points,
        "review_source": scraper.name,           # apify | web_fallback
        "search_keyword": search_keyword,         # 实际传给 Amazon search 的关键词（含翻译+相关性校验链路）
        "review_count": len(items),
        "platforms": platforms,
        "fallback_reason": fallback_reason,       # None 表示走 Apify 真实评论
        "purchase_motivations": ["便携性", "使用便利性", "适合特定生活方式场景"],
        "negative_review_patterns": final_pain_points[:5],
        "opportunity_insights": [
            "将高频抱怨点转化为产品改进点。",
            "在 Listing 中明确使用场景和限制，降低预期偏差。",
        ],
        "pain_point_score": 8.0 if len(final_pain_points) >= 3 else 5.5,
        "evidence": evidence,
        "confidence": round(min(0.9, 0.3 + len(final_pain_points) * 0.08), 2),
        "pain_points_language": language,
    }

    status = "success" if final_pain_points else "partial"
    warning = None if final_pain_points else "review pain point data limited"
    state["audit_log"].append(
        {
            "agent": "ReviewInsightAgent",
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": len(evidence),
            "confidence": state["review_result"].get("confidence", 0.0),
            "warning": warning,
            "review_source": scraper.name,
            "search_keyword": search_keyword,
            "review_count": len(items),
            "platforms": platforms,
            "fallback_reason": fallback_reason,
        }
    )
    state["errors"].extend(
        [{"agent": "ReviewInsightAgent", "error": str(fr)} for fr in [fallback_reason] if fr and "failed" in str(fr)]
    )
    return state
