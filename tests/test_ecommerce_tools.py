"""EcomResearcher 工具层单测：标准化、查询构造、评论抽取、注入式搜索。"""

import pytest

from multi_agents.ecommerce.tools.product_search import (
    build_ecommerce_queries,
    search_sources,
)
from multi_agents.ecommerce.tools.review_extractor import extract_review_insights
from multi_agents.ecommerce.tools.source_normalizer import normalize_source


def test_normalize_source_accepts_href_and_body():
    source = normalize_source(
        {
            "title": "Best Portable Blenders",
            "href": "https://example.com/blenders",
            "body": "Customers complain about battery life.",
        }
    )

    assert source["title"] == "Best Portable Blenders"
    assert source["url"] == "https://example.com/blenders"
    assert source["source_type"] == "blog"
    assert "battery life" in source["snippet"]


def test_normalize_source_infers_amazon_type():
    source = normalize_source(
        {"title": "Amazon", "url": "https://www.amazon.com/dp/xxx", "snippet": "x"}
    )
    assert source["source_type"] == "amazon"


def test_build_ecommerce_queries_returns_bounded_queries():
    queries = build_ecommerce_queries(
        query="portable blender",
        target_market="US",
        intent="review",
        max_queries=3,
    )

    assert len(queries) == 3
    assert "portable blender" in queries[0]
    assert any("complaints" in item for item in queries)


def test_build_ecommerce_queries_unknown_intent_falls_back_to_trend():
    queries = build_ecommerce_queries(
        query="standing desk",
        target_market="US",
        intent="nonexistent",
        max_queries=2,
    )
    assert len(queries) == 2
    assert all("standing desk" in q for q in queries)


def test_extract_review_insights_finds_complaint_sentences():
    sources = [
        {
            "title": "Review",
            "url": "https://example.com/review",
            "source_type": "blog",
            "snippet": "Users complain the product leaks and has poor battery life.",
            "content": "Many customers say it is difficult to clean.",
        }
    ]

    insights = extract_review_insights(sources)

    assert any("leaks" in item for item in insights)
    assert any("difficult to clean" in item for item in insights)


def test_extract_review_insights_respects_limit():
    sources = [
        {
            "title": "Bulk",
            "url": f"https://example.com/{i}",
            "snippet": "It leaks. It is bad. Battery poor. Noise too loud.",
            "content": "",
        }
        for i in range(5)
    ]
    insights = extract_review_insights(sources, limit=3)
    assert len(insights) == 3


@pytest.mark.asyncio
async def test_search_sources_uses_injected_search_function():
    async def fake_search(query: str, max_results: int):
        return [{"title": query, "href": "https://example.com", "body": "result body"}]

    sources = await search_sources(
        queries=["portable blender reviews"],
        search_fn=fake_search,
        max_results_per_query=1,
    )

    assert len(sources) == 1
    assert sources[0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_search_sources_dedupes_by_url():
    async def fake_search(query: str, max_results: int):
        return [
            {"title": "dup", "href": "https://example.com/same", "body": "a"},
            {"title": "dup", "href": "https://example.com/same", "body": "b"},
            {"title": "other", "href": "https://example.com/other", "body": "c"},
        ]

    sources = await search_sources(
        queries=["q"],
        search_fn=fake_search,
        max_results_per_query=3,
    )

    assert len(sources) == 2
    urls = [s["url"] for s in sources]
    assert "https://example.com/same" in urls
    assert "https://example.com/other" in urls


def test_normalize_source_falls_back_to_hostname_when_no_title():
    """raw 没 title/name 时，title 用 url 主机名兜底（去 www），比 'Untitled source' 有辨识度。

    真实场景：Tavily 默认检索器不返回 title，旧逻辑全兜底成 'Untitled source'，
    导致报告引用全是 [Untitled source](url)，丢失来源辨识度。
    """
    source = normalize_source(
        {"href": "https://www.360researchreports.com/market-reports/x", "body": "..."}
    )
    assert source["title"] == "360researchreports.com"  # 去掉 www. 前缀
    assert source["url"] == "https://www.360researchreports.com/market-reports/x"


def test_normalize_source_keeps_untitled_when_url_empty():
    """raw 既没 title、url 也空/不安全时，才兜底成 'Untitled source'（最后兜底）。"""
    source = normalize_source({"body": "no title no url"})
    assert source["title"] == "Untitled source"
    assert source["url"] == ""
