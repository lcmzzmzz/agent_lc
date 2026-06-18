# Apify 检索源接入指南（抓真实 Amazon 评论）

> 默认检索源是 Tavily（搜公开网页摘要）。本文教你切换成 **Apify**，直接抓 Amazon 真实评论/产品数据，让「用户痛点」一节基于真实买家反馈，而不是网页评测。

---

## 1. 为什么用 Apify

| 检索源 | 数据 | 评论真实性 | 成本 |
|--------|------|-----------|------|
| Tavily（默认） | 公开网页摘要（博客/评测/论坛） | 间接（多为评测文章） | 按调用计费，便宜 |
| **Apify** | Amazon 真实商品/评论数据 | **直接（真实买家评论）** | Apify 按量计费，有免费额度 |

痛点分析（ReviewInsightAgent）用真实 Amazon 评论效果最好。Apify 是现成的爬虫平台，不用自己写反爬。

---

## 2. 前置：注册 Apify + 拿 API token

1. 注册：https://console.apify.com/（可用 Google/GitHub 登录）
2. 进 **Settings → Integrations → API tokens**
3. 复制你的 **Personal API token**（一长串）

> Apify 有免费额度（每月 $5 平台额度 + 部分 actor 免费），轻度测试够用。

---

## 3. 选择 Amazon 两步 Actor

ReviewInsightAgent 现在走的是“两步真实评论抓取”：

1. 关键词搜索产品，拿 Amazon ASIN
2. 用 ASIN 抓该商品的真实评论

当前默认 actor：

- 产品搜索：`igview-owner~amazon-search-scraper`
- 评论抓取：`web_wanderer~amazon-reviews-extractor`

> Apify API 的 actorId 在 `run-sync-get-dataset-items` URL 里建议使用 `用户名~actor名` 格式，例如 `igview-owner~amazon-search-scraper`。不同 actor 的**输入字段**（keyword / asin / urls / products）和**输出字段**（reviewText / content / body）不一样。换 actor 后如果结果对不上，优先改 `multi_agents/ecommerce/tools/review_scraper.py` 里的 payload 和 `_map_amazon_review()` 映射。

---

## 4. 配置 .env

在项目根目录 `.env` 里加：

```bash
# 1) Apify token（第 2 步拿到的）
APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxx

# 2) 可选：ReviewInsightAgent 的产品搜索 actor（关键词 -> ASIN）
APIFY_AMAZON_SEARCH_ACTOR=igview-owner~amazon-search-scraper

# 3) 可选：ReviewInsightAgent 的评论抓取 actor（ASIN -> 评论）
APIFY_AMAZON_REVIEWS_ACTOR=web_wanderer~amazon-reviews-extractor

# 4) 可选：Amazon 站点国家（默认 US）
APIFY_AMAZON_COUNTRY=US

# 5) 可选：把趋势/竞品等普通检索也切到 Apify；不设则仍用 Tavily
ECOMMERCE_SEARCH_BACKEND=apify
```

> ⚠️ token 是密钥，`.env` 已在 `.gitignore` 里，不会被提交。**不要**把 token 写进代码或文档。

> `APIFY_REVIEW_ACTOR` 是旧的单 actor 搜索源变量，只会被 `multi_agents/ecommerce/tools/apify_search.py` 读取。当前 ReviewInsightAgent 的真实评论链路读取的是 `APIFY_AMAZON_SEARCH_ACTOR` 和 `APIFY_AMAZON_REVIEWS_ACTOR`。

---

## 5. 启用并验证

配好 `.env` 后，正常跑即可。只要 `APIFY_API_TOKEN` 存在，ReviewInsightAgent 会优先尝试 Apify 真实评论；如果 Apify 返回 0 条或失败，会自动降级到 Tavily fallback：

```bash
# CLI
python -m multi_agents.ecommerce --query "portable blender" --depth standard

# 或前端（启动后端后访问研究页）
python -m uvicorn main:app --port 8000
#   http://localhost:8000/site/ecommerce.html
```

**验证是否生效**：看日志（控制台或 `logs/ecommerce/<时间戳>_<关键词>.log`）：

```
[ReviewInsight] 开始 query='portable blender' scraper=apify platforms=['amazon', 'reddit']
[apify:amazon] 第一步 search 拿到 ASIN: ['B0XXX1', 'B0XXX2']
[apify:amazon] 第二步 reviews 抓取到 8 条评论
[ReviewInsight] 抓取完成 source=apify review_count=8 fallback_reason=None
```

如果 free plan 或 actor 限制导致评论抓不到，日志会显示：

```
[ReviewInsight] Apify 返回 0 条评论，降级 Tavily fallback
[ReviewInsight] 抓取完成 source=web_fallback review_count=6 fallback_reason=apify returned 0 reviews
```

报告「用户痛点」一节仍会产出，但 `review_source=web_fallback` 会明确标记它来自 Tavily 兜底，而不是 Amazon 真实评论。

---

## 6. 切回 Tavily

把 `.env` 里 `ECOMMERCE_SEARCH_BACKEND` 改回 `tavily`（或删掉这行 / 注释掉）：

```bash
ECOMMERCE_SEARCH_BACKEND=tavily
```

或直接不设该变量（默认就是 Tavily）。

---

## 7. 排错

| 现象 | 原因 / 处理 |
|------|------|
| 启动报 `APIFY_API_TOKEN 未配置` | `.env` 没加 token，或没 `load_dotenv`（CLI/API 入口已自动加载） |
| 日志 `Apify 不可用(...)，回退 Tavily` | token 无效或 actor 跑挂了，自动降级 Tavily，不影响出报告 |
| `[apify:amazon] 第一步 search 未拿到任何 ASIN` | 产品搜索 actor 的 input 字段名不对，或该 actor 不支持关键词搜索；查 actor 文档，改 `review_scraper.py` 的 `_search_asins()` payload |
| `[apify:amazon] 第二步 reviews 抓取到 0 条评论` | 评论 actor 需要付费 proxy/Pay-Per-Result，或 input 字段不是 `products`；查 actor 文档，改 `_fetch_reviews()` payload |
| 结果字段对不上（review_text 空） | actor 输出字段名不同；改 `_map_amazon_review()` 的字段映射 |
| 超时 / 很慢 | Amazon 评论 actor 跑一次可能几十秒~几分钟；`run-sync` 会等，正常现象 |
| 402 / 额度不足 | Apify 免费额度用完，充值或换免费 actor |

---

## 8. 设计说明

- **双数据源**：ReviewInsightAgent 优先通过 `ApifyReviewScraper` 抓真实 Amazon 评论；失败或无 token 时使用 `FallbackSearchReviewScraper` 从 Tavily 网页摘要抽取评论句。
- **两步抓取**：Amazon 评论 actor 通常只接受 ASIN/URL，不接受品类词，所以先通过产品搜索 actor 拿 ASIN，再用评论 actor 抓评论正文。
- **可降级**：Apify 不可用时自动回退 Tavily，保证流程不崩。
- **可扩展**：以后接 Reddit / TikTok / Google Maps 评论时，只要实现新的 `ReviewSource` 或扩展 `ApifyReviewScraper.SUPPORTED_PLATFORMS`，Agent 层不用改。

## 真实测试结论（2026-06-18，free plan 实测）

Apify free plan（$5 额度）实测各平台 actor 的真实表现：

| 平台 | actor | 结果 |
|------|-------|------|
| Amazon 搜产品（keyword→ASIN） | `igview-owner~amazon-search-scraper` | ✅ 拿到真实 ASIN（第一步通） |
| Amazon 抓评论（ASIN→评论） | `web_wanderer~amazon-reviews-extractor` | ❌ 返回 0 条（free plan 抓不到，需付费 residential proxy） |
| Google Maps 评论 | `compass~Google-Maps-Reviews-Scraper` | ❌ run FAILED（Pay-Per-Result 付费 actor） |
| TikTok 评论 | `clockworks~tiktok-comments-scraper` | 需具体视频 URL，未测 |

**结论**：Amazon 评论反爬最强，热门评论 actor 多为 Pay-Per-Result，free plan 抓不到评论正文。但**架构与降级完全工作**：
- 第一步（关键词→ASIN）真实可用
- 第二步评论抓取失败时自动降级 Tavily（`review_source=web_fallback`），DeepSeek 照常归纳中文痛点，报告照常产出（HTTP 200）
- 想抓真实评论：充值 / 开 residential proxy / 换付费 actor，**token 不变即可生效**（代码侧 `ApifyReviewScraper` 已实现两步 + 多平台接口预留）

> 这套「Apify 失败 → 自动降级 Tavily」的容错，本身就是项目的一个工程亮点。
