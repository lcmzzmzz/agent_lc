"""评论抓取层（双数据源）单测：不依赖真实 Apify key，全 mock。"""

import pytest

from multi_agents.ecommerce.tools.review_scraper import (
    ApifyReviewScraper,
    FallbackSearchReviewScraper,
    ReviewItem,
    _category_terms,
    _filter_relevant_products,
    get_review_scraper,
)
from multi_agents.ecommerce.runtime.budget_manager import BudgetConfig, BudgetManager
from multi_agents.ecommerce.runtime.telemetry import empty_governance_state, summarize_governance


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
            return _FakeResp([
                {"asin": "B0XXX1", "title": "Portable USB Rechargeable Blender"},
                {"asin": "B0XXX2", "title": "Mini Personal Blender for Shakes"},
            ])
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


@pytest.mark.asyncio
async def test_apify_scraper_respects_external_api_budget(monkeypatch):
    called = False

    def fake_post(url, json=None, params=None, timeout=None):
        nonlocal called
        called = True
        return _FakeResp([])

    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
    import multi_agents.ecommerce.tools.review_scraper as mod

    monkeypatch.setattr(mod.requests, "post", fake_post)

    governance = empty_governance_state()
    budget = BudgetManager(governance, BudgetConfig(max_external_api_calls=0))
    scraper, _ = get_review_scraper(governance=governance, budget_manager=budget)

    items = await scraper.scrape("portable blender", ["amazon"], 5)

    assert items == []
    assert called is False
    summary = summarize_governance(governance)
    assert summary["external_api_call_count"] == 0
    assert summary["degraded_by_budget"] is True


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


@pytest.mark.asyncio
async def test_fallback_scraper_uses_target_market_in_queries():
    seen_queries = []

    async def fake_search(query, max_results):
        seen_queries.append(query)
        return [
            {
                "title": "Review",
                "href": "https://example.com/de-review",
                "body": "Customers complain about battery life.",
            }
        ]

    scraper = FallbackSearchReviewScraper(fake_search, target_market="DE")
    await scraper.scrape("portable blender", ["amazon"], 3)

    assert seen_queries
    assert any("DE" in query for query in seen_queries)


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


@pytest.mark.asyncio
async def test_review_insight_fallback_preserves_target_market(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")

    import multi_agents.ecommerce.tools.review_scraper as mod

    monkeypatch.setattr(mod.requests, "post", lambda *a, **k: _FakeResp([]))

    seen_queries = []

    async def fake_search(query, max_results):
        seen_queries.append(query)
        return [
            {
                "title": "R",
                "href": "https://example.com/de-r",
                "body": "Customers complain about battery life.",
            }
        ]

    from multi_agents.ecommerce.agents.planner import run_planner
    from multi_agents.ecommerce.agents.review_insight import run_review_insight
    from multi_agents.ecommerce.state import create_initial_state

    state = run_planner(create_initial_state("portable blender", target_market="DE"))
    updated = await run_review_insight(state, search_fn=fake_search)

    assert updated["review_result"]["review_source"] == "web_fallback"
    assert seen_queries
    assert any("DE" in query for query in seen_queries)


# ---------------------------------------------------------------------------
# 产品相关性校验：挡掉「搜音箱返回手机」这类跑偏
# ---------------------------------------------------------------------------


def test_category_terms_strips_generic_modifiers():
    # bluetooth/wireless/portable 是通用修饰词，过滤后只剩品类核心词
    assert _category_terms("bluetooth speaker") == ["speaker"]
    assert _category_terms("portable blender") == ["blender"]
    assert _category_terms("automatic pet feeder") == ["automatic", "pet", "feeder"]
    assert _category_terms("蓝牙音箱") == []  # 纯中文取不到英文 token


def test_filter_relevant_products_passes_matching():
    products = [
        {"asin": "A1", "title": "Portable Bluetooth Speaker"},
        {"asin": "A2", "title": "Waterproof Speaker"},
    ]
    relevant = _filter_relevant_products(products, "bluetooth speaker")
    assert len(relevant) == 2  # 两个都含品类词 speaker


def test_filter_relevant_products_blocks_phones_as_speakers():
    # 复现真实 bug：搜蓝牙音箱，Apify 返回三星手机（标题含 bluetooth 但不含 speaker）
    products = [
        {"asin": "B0G4SW96R4", "title": "Samsung Galaxy S26 Unlocked Smartphone"},
        {"asin": "B0FXY18C1J", "title": "Samsung Galaxy A17 5G Smart Phone"},
    ]
    relevant = _filter_relevant_products(products, "bluetooth speaker")
    assert relevant == []  # 手机不含品类词 speaker → 拦截，绝不拿手机评论冒充音箱


@pytest.mark.asyncio
async def test_apify_scraper_irrelevant_search_returns_empty(monkeypatch):
    """集成验证：search 返回不相关产品（手机）→ scrape 返回 []（交给上层降级）。"""
    def fake_post(url, json=None, params=None, timeout=None):
        if "amazon-search-scraper" in url:
            return _FakeResp([
                {"asin": "B0G4SW96R4", "title": "Samsung Galaxy S26 Smartphone"},
                {"asin": "B0FXY18C1J", "title": "Samsung Galaxy A17 Smart Phone"},
            ])
        return _FakeResp([  # reviews actor 本能抓到，但不会走到这步
            {"rating": "4", "reviewText": "great phone", "productUrl": "x"}
        ])

    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
    import multi_agents.ecommerce.tools.review_scraper as mod
    monkeypatch.setattr(mod.requests, "post", fake_post)

    scraper, _ = get_review_scraper()
    items = await scraper.scrape("bluetooth speaker", ["amazon"], 5)
    assert items == []  # 相关性校验拦截，绝不返回手机评论


# ---------------------------------------------------------------------------
# keyword 中英映射：_to_search_keyword
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_to_search_keyword_translates_chinese():
    async def fake_llm(system, user):
        return "bluetooth speaker"

    from multi_agents.ecommerce.agents.review_insight import _to_search_keyword
    kw = await _to_search_keyword(fake_llm, "蓝牙音箱")
    assert kw == "bluetooth speaker"


@pytest.mark.asyncio
async def test_to_search_keyword_falls_back_without_llm():
    from multi_agents.ecommerce.agents.review_insight import _to_search_keyword
    kw = await _to_search_keyword(None, "蓝牙音箱")
    assert kw == "蓝牙音箱"  # 无 llm_fn → 回退原 query


@pytest.mark.asyncio
async def test_to_search_keyword_strips_punctuation():
    async def fake_llm(system, user):
        return "Bluetooth Speaker, best 2026!"

    from multi_agents.ecommerce.agents.review_insight import _to_search_keyword
    kw = await _to_search_keyword(fake_llm, "蓝牙音箱")
    assert "," not in kw and "!" not in kw
    assert "bluetooth speaker" in kw


@pytest.mark.asyncio
async def test_review_insight_passes_search_keyword(monkeypatch):
    """Apify search 返回相关产品 → 正常抓评论，且 review_source=apify、记录 search_keyword。"""
    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
    captured = {"search_keywords": []}

    def fake_post(url, json=None, params=None, timeout=None):
        if "amazon-search-scraper" in url:
            if isinstance(json, dict):
                captured["search_keywords"].append(json.get("query"))
            return _FakeResp([{"asin": "B0SPK1", "product_title": "Portable Bluetooth Speaker"}])
        if "amazon-reviews-extractor" in url:
            return _FakeResp([{"rating": "5", "reviewText": "Loud and clear sound.", "productUrl": "x"}])
        return _FakeResp([])

    import multi_agents.ecommerce.tools.review_scraper as mod
    monkeypatch.setattr(mod.requests, "post", fake_post)

    async def fake_llm(system, user):
        return "bluetooth speaker"  # 翻译

    from multi_agents.ecommerce.agents.planner import run_planner
    from multi_agents.ecommerce.agents.review_insight import run_review_insight
    from multi_agents.ecommerce.state import create_initial_state

    state = run_planner(create_initial_state("蓝牙音箱"))
    updated = await run_review_insight(state, search_fn=None, llm_fn=fake_llm)

    rr = updated["review_result"]
    assert rr["search_keyword"] == "bluetooth speaker"   # 翻译生效
    assert rr["review_source"] == "apify"                 # 相关产品通过校验，未降级
    assert "bluetooth speaker" in captured["search_keywords"]  # 翻译后的英文 query 真的传给了 Amazon search
    assert rr["review_count"] >= 1


@pytest.mark.asyncio
async def test_search_products_uses_query_field_and_maps_product_title(monkeypatch):
    """字段名修复的物证（真因回归测试）。

    actor 实际认的 input 字段是 query（不是 keyword）、产品名字段是 product_title（不是 title）。
    本测试断言：发送的 input 用 query 且无 keyword；product_title 被映射到 title；富字段被捕获。
    这正是「搜蓝牙音箱返回三星手机 + title 恒空」两个 bug 的回归防护。
    """
    captured = {}

    def fake_post(url, json=None, params=None, timeout=None):
        captured["json"] = json
        return _FakeResp([{
            "asin": "B0SPK1",
            "product_title": "Anker Soundcore 2 Portable Bluetooth Speaker",
            "product_price": "$39.99",
            "product_star_rating": "4.5",
            "product_num_ratings": 1234,
            "sales_volume": "10K+ bought in past month",
            "is_amazon_choice": True,
            "is_best_seller": False,
            "product_url": "https://amazon.com/dp/B0SPK1",
        }])

    monkeypatch.setenv("APIFY_API_TOKEN", "fake-token")
    import multi_agents.ecommerce.tools.review_scraper as mod
    monkeypatch.setattr(mod.requests, "post", fake_post)

    scraper, _ = get_review_scraper()
    products = await scraper._search_products("bluetooth speaker", limit=5)

    # ① input 字段名修复：actor 认 query，不认 keyword
    assert captured["json"].get("query") == "bluetooth speaker"
    assert "keyword" not in captured["json"]
    assert captured["json"].get("maxPages") == 1
    # ② product_title（actor 真实字段）映射到 title，title 不再恒空
    assert len(products) == 1
    p = products[0]
    assert p["asin"] == "B0SPK1"
    assert "Soundcore" in p["title"]
    # ③ 富字段捕获（销量/评分/badge 是 Amazon 选品金矿，评论路径顺带带回）
    assert p["rating"] == 4.5
    assert p["num_ratings"] == 1234
    assert "10K+" in p["sales_volume"]
    assert p["is_amazon_choice"] is True
    assert p["is_best_seller"] is False
