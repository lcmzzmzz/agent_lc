"""评论抓取层（双数据源）单测：不依赖真实 Apify key，全 mock。"""

import pytest

from multi_agents.ecommerce.tools.review_scraper import (
    ApifyReviewScraper,
    FallbackSearchReviewScraper,
    ReviewItem,
    get_review_scraper,
)


# ---------------------------------------------------------------------------
# 工厂：无 token → Fallback；有 token → Apify
# ---------------------------------------------------------------------------


def test_get_review_scraper_no_token_returns_fallback(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)

    async def fake_search(q, n):
        return []

    scraper, reason = get_review_scraper(fake_search)
    assert scraper.name == "web_fallback"
    assert reason and "no APIFY_API_TOKEN" in reason


def test_get_review_scraper_with_token_returns_apify(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")

    scraper, reason = get_review_scraper()
    assert scraper.name == "apify"
    assert reason is None
    assert "amazon_search" in scraper.actors and "amazon_reviews" in scraper.actors


# ---------------------------------------------------------------------------
# Apify 映射（mock requests.post）
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.content = b"x" if payload is not None else b""

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_apify_scraper_two_step_amazon(monkeypatch):
    # 两步 mock：按 actor URL 分派 —— search actor 返回 ASIN，reviews actor 返回评论
    def fake_post(url, json=None, params=None, timeout=None):
        assert params["token"] == "fake-token"
        if "amazon-search-scraper" in url:
            return _FakeResp([{"asin": "B0XXX1"}, {"asin": "B0XXX2"}])
        if "amazon-reviews-extractor" in url:
            return _FakeResp([
                {"rating": "4", "reviewText": "Works but battery dies fast.",
                 "productUrl": "https://amazon.com/dp/B0XXX1"},
                {"rating": "1", "reviewText": "Caught fire after a week.",
                 "productUrl": "https://amazon.com/dp/B0XXX2"},
            ])
        return _FakeResp([])

    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
    import multi_agents.ecommerce.tools.review_scraper as mod

    monkeypatch.setattr(mod.requests, "post", fake_post)

    scraper, _ = get_review_scraper()
    items = await scraper.scrape("portable blender", ["amazon"], 5)

    assert scraper.name == "apify"
    assert len(items) == 2
    assert all(it.platform == "amazon" for it in items)
    assert items[0].get("rating") == 4.0
    assert "battery" in items[0].review_text
    assert items[1].get("rating") == 1.0


@pytest.mark.asyncio
async def test_apify_scraper_search_empty_returns_nothing(monkeypatch):
    # 第一步 search 拿不到 ASIN → 第二步不调，返回空
    def fake_post(url, json=None, params=None, timeout=None):
        if "amazon-search-scraper" in url:
            return _FakeResp([])  # 没搜到产品
        return _FakeResp([])

    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
    import multi_agents.ecommerce.tools.review_scraper as mod

    monkeypatch.setattr(mod.requests, "post", fake_post)

    scraper, _ = get_review_scraper()
    items = await scraper.scrape("portable blender", ["amazon"], 5)
    assert items == []


@pytest.mark.asyncio
async def test_apify_scraper_failure_returns_empty(monkeypatch):
    def fake_post(url, json=None, params=None, timeout=None):
        raise RuntimeError("apify 500")

    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
    import multi_agents.ecommerce.tools.review_scraper as mod

    monkeypatch.setattr(mod.requests, "post", fake_post)

    scraper, _ = get_review_scraper()
    items = await scraper.scrape("portable blender", ["amazon"], 5)
    assert items == []  # 失败不抛，返回空（由 review_insight 决定降级）


# ---------------------------------------------------------------------------
# Fallback：用 fake_search 抽评论句
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_scraper_extracts_from_search():
    async def fake_search(query, max_results):
        return [
            {
                "title": "Review",
                "href": f"https://example.com/{i}",
                "body": "Customers complain about battery life and leaking.",
            }
            for i in range(2)
        ]

    scraper = FallbackSearchReviewScraper(fake_search)
    items = await scraper.scrape("portable blender", ["amazon", "reddit"], 6)

    assert scraper.name == "web_fallback"
    assert len(items) >= 1
    assert all(it.platform == "web" for it in items)
    assert any("battery" in it.review_text or "leak" in it.review_text for it in items)


# ---------------------------------------------------------------------------
# review_insight 集成：Apify 空 → 自动降级 Fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_insight_falls_back_when_apify_empty(monkeypatch):
    # 有 token → 走 Apify，但 mock 返回空 → 应降级 Fallback
    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")

    import multi_agents.ecommerce.tools.review_scraper as mod

    monkeypatch.setattr(mod.requests, "post", lambda *a, **k: _FakeResp([]))

    async def fake_search(query, max_results):
        return [
            {"title": "R", "href": "https://example.com/r",
             "body": "Customers complain about battery life."}
        ]

    from multi_agents.ecommerce.agents.planner import run_planner
    from multi_agents.ecommerce.agents.review_insight import run_review_insight
    from multi_agents.ecommerce.state import create_initial_state

    state = run_planner(create_initial_state("portable blender"))
    updated = await run_review_insight(state, search_fn=fake_search)

    rr = updated["review_result"]
    # Apify 返回空 → 降级到 web_fallback
    assert rr["review_source"] == "web_fallback"
    assert rr["fallback_reason"] and "0 reviews" in rr["fallback_reason"]
    assert rr["review_count"] >= 1
    # audit_log 含降级信息
    audit = [a for a in updated["audit_log"] if a["agent"] == "ReviewInsightAgent"][0]
    assert audit["review_source"] == "web_fallback"
    assert audit["fallback_reason"] is not None
