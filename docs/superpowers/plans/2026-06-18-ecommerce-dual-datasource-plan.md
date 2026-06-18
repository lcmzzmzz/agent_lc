# EcomResearcher 双数据源架构（Tavily + Apify）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 superpowers:executing-plans 逐任务实现。步骤用 `- [ ]` 跟踪。

**Goal:** 把评论数据源升级为可插拔的双层架构：Tavily 负责广域检索（趋势/竞品/评测/风险），Apify 负责平台级真实评论抓取（Amazon 优先，多平台预留）。ReviewInsightAgent 优先用真实评论，Apify 不可用时自动降级到 Tavily 摘要，全程可观测（review_source / review_count / platforms / fallback_reason）。

**Architecture:** 新增 `review_scraper.py` 作为评论抓取层，定义统一接口 `scrape_reviews(query, platforms, max_reviews) -> list[ReviewItem]`，内含两个可插拔实现：`ApifyReviewScraper`（真实 Amazon 评论）与 `FallbackSearchReviewScraper`（包装现有 Tavily search + 关键词抽取）。`ReviewInsightAgent` 通过工厂 `get_review_scraper()` 拿到当前可用的 scraper（有 Apify token 用 Apify，否则 fallback），Apify 失败时自动降级。广域检索（trend/competitor/risk）继续走 Tavily，不动。

**Tech Stack:** Python, pytest, Apify REST API, requests, TypedDict。

**MVP 范围:** Apify 实现先做 **Amazon 评论**（一个 actor），`ReviewSource` 接口与 `platforms` 参数预留多平台（TikTok/YouTube/Reddit/Google Maps 后续按需加 Scraper）。

---

## 简历表达（目标）

> 设计 Tavily + Apify 双数据源架构：Tavily 负责开放网页检索（趋势/竞品/评测/风险），Apify 负责平台级真实评论抓取（Amazon），评论洞察从「摘要检索」升级为「真实用户反馈分析」，并通过可插拔 Scraper + 自动降级保证无 token 时演示仍可跑。

---

## 数据源分工

| 层 | 数据源 | 负责 | 适用 Agent |
|----|--------|------|-----------|
| 广域检索 | **Tavily**（默认检索器） | 市场趋势 / 竞品资料 / 评测文章 / Reddit·blog·对比页 / 风险合规行业报告 | TrendResearchAgent、CompetitorAnalysisAgent、报告引用 |
| 平台评论 | **Apify**（可插拔 Scraper） | Amazon 真实评论（rating/date/helpful/product_url），后续 TikTok/YouTube/Reddit/GMaps | ReviewInsightAgent |

---

## File Structure

### Create
- `multi_agents/ecommerce/tools/review_scraper.py` — 评论抓取层
  - `ReviewItem` (TypedDict): `platform / rating / review_text / date / helpful / product_url / title / source_url / raw`
  - `ReviewSource` (Protocol/ABC): `async scrape(query, platforms, max_reviews) -> list[ReviewItem]` + `name` 属性
  - `ApifyReviewScraper` — 调 Apify Amazon 评论 actor，返回结构化 `ReviewItem`（复用 `apify_search.py` 的 token/actor/调用逻辑，或迁入）
  - `FallbackSearchReviewScraper` — 包装现有 `search_sources` + `extract_review_insights`，把抽取的句子包成 `ReviewItem`（review_text=句子，source_url=网页 url）
  - `get_review_scraper()` — 工厂：`APIFY_API_TOKEN` 存在 → `ApifyReviewScraper`；否则 → `FallbackSearchReviewScraper`
- `tests/test_ecommerce_review_scraper.py` — 三种场景测试

### Modify
- `multi_agents/ecommerce/agents/review_insight.py` — 优先用 `get_review_scraper()`，audit_log 加 `review_source / review_count / platforms / fallback_reason`；保留 LLM 中文归纳
- `multi_agents/ecommerce/evaluation.py` — 评估摘要加 `review_source / review_count`
- `multi_agents/ecommerce/tools/apify_search.py` — 复用其 token/actor 逻辑（被 `ApifyReviewScraper` 调用，或合并；保留 `_map_item` 思路但产出 `ReviewItem`）
- `README.md` / `docs/ecommerce-researcher.md` — 加「双数据源架构」说明段

---

## Task 1: ReviewItem + ReviewSource 接口 + 工厂

**Files:** Create `multi_agents/ecommerce/tools/review_scraper.py`（接口与工厂骨架）

- [ ] 定义 `ReviewItem` TypedDict（platform/rating/review_text/date/helpful/product_url/title/source_url/raw）
- [ ] 定义 `ReviewSource` 协议：`name: str` + `async scrape(query, platforms, max_reviews) -> list[ReviewItem]`
- [ ] `get_review_scraper()`：读 `APIFY_API_TOKEN`，有→Apify（暂用占位实现，Task 2 填充），无→Fallback（Task 3 填充）；返回 `(scraper, fallback_reason)` 便于审计（fallback_reason 在选 Apify 时为 None）
- [ ] 写测试：`get_review_scraper()` 在无 token 时返回 Fallback + fallback_reason；有 token 时返回 Apify

---

## Task 2: ApifyReviewScraper（真实 Amazon 评论）

**Files:** Modify `review_scraper.py`；复用 `apify_search.py` 的 token/actor/HTTP 逻辑

- [ ] `ApifyReviewScraper.scrape()`：调 Apify Amazon 评论 actor（`APIFY_REVIEW_ACTOR`，默认 `compass/listing-amazon-reviews`），把返回 item 映射成 `ReviewItem`（rating/review_text/date/helpful/product_url）
- [ ] 失败（token 无效 / actor 报错 / 超时 / 0 条）→ 抛 `ReviewScrapeError` 或返回空列表 + 让上层决定降级
- [ ] 用 monkeypatch/fake HTTP 测试：mock requests.post 返回固定评论 JSON，断言映射成 ReviewItem（含 rating/review_text）
- [ ] 不依赖真实 token（测试 mock）

---

## Task 3: FallbackSearchReviewScraper（Tavily 摘要兜底）

**Files:** Modify `review_scraper.py`；包装现有 `search_sources` + `extract_review_insights`

- [ ] `FallbackSearchReviewScraper.scrape()`：用注入的 `search_fn` 调 `search_sources` 拿网页，再 `extract_review_insights` 抽句子，每句包成 `ReviewItem`（platform="web", review_text=句子, source_url=网页 url, rating=None）
- [ ] 接收 `search_fn` 参数（注入式，测试用 fake_search）
- [ ] 测试：fake_search 返回带抱怨词的网页 → scrape 返回 ReviewItem 列表（review_text 非空）

---

## Task 4: ReviewInsightAgent 接入双数据源

**Files:** Modify `multi_agents/ecommerce/agents/review_insight.py`

- [ ] 改为优先调 `get_review_scraper().scrape_reviews(query, platforms, max_reviews)` 拿评论
- [ ] Apify 路径：拿到真实 ReviewItem → LLM 归纳中文痛点（已有 `_summarize_pain_points_zh`，改为接收 ReviewItem 的 review_text）
- [ ] Apify 失败/无 token → 自动 fallback 到 FallbackSearchReviewScraper（工厂已在无 token 时选 Fallback；Apify 运行时失败则 review_insight 内部 catch 后切 Fallback）
- [ ] audit_log 加字段：`review_source`（apify/web_fallback）、`review_count`、`platforms`、`fallback_reason`（None 或原因）
- [ ] 保留 `pain_points_language` 字段
- [ ] 测试：mock scraper 返回真实评论 → review_result 含 pain_points + review_source=apify；mock Apify 失败 → review_source=web_fallback + fallback_reason 非空

---

## Task 5: evaluation 指标扩展

**Files:** Modify `multi_agents/ecommerce/evaluation.py`

- [ ] `build_evaluation_summary()` 增加 `review_source`（从 review_result 或 audit_log 取）和 `review_count`
- [ ] 测试：fake_state 含 review_result.review_source/review_count → summary 含这两个字段

---

## Task 6: README / docs 双数据源说明

**Files:** Modify `README.md` / `docs/ecommerce-researcher.md` / `docs/ecommerce-portfolio-notes.md`

- [ ] 加「双数据源架构」段：Tavily 广域 + Apify 平台评论分工表 + 降级说明
- [ ] portfolio-notes 简历要点加双数据源那条
- [ ] 链接到 `docs/ecommerce-apify-setup.md`

---

## Self-Review

### Spec coverage
- 双数据源分工：Tavily（广域）/ Apify（评论）— Task 4 + 文档
- 可插拔 Scraper（Apify + Fallback）— Task 1/2/3
- ReviewInsightAgent 优先真实评论 + 降级 — Task 4
- 可观测（review_source/count/platforms/fallback_reason）— Task 4/5
- 不强绑定（无 token 走 Tavily，demo 可跑）— 工厂 + Fallback
- 测试（Apify 成功/失败/无 token）— Task 2/3/4
- README 双数据源 — Task 6

### MVP 边界
- Apify 仅 Amazon（一个 actor），接口预留多平台
- 不动 trend/competitor/risk（继续 Tavily）

### Type consistency
- `ReviewItem` 字段在 scraper / review_insight / evaluation 一致
- `review_source` 取值枚举：`apify` | `web_fallback`
- `get_review_scraper()` 返回签名在 Task 1 定，Task 4 消费

---

## 风险与降级（核心设计原则）

- **无 APIFY_API_TOKEN** → 工厂直接返回 FallbackSearchReviewScraper，demo 照跑（当前行为）
- **Apify token 有但调用失败**（actor 报错/超时/0 条）→ review_insight 捕获，切 Fallback，记录 fallback_reason
- **Apify 返回但字段对不上** → `_map_item` 兜底字段，空值容忍，不崩
- 广域检索（trend/competitor）完全不受影响，始终 Tavily
