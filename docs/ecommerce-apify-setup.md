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

## 3. 选一个 Amazon 评论 Actor

在 Apify Store 搜 "amazon reviews"，挑一个，记下它的 actor ID（格式 `用户名/actor名`）。例如：

- `compass/listing-amazon-reviews`
- `natasuraj/amazon-reviews`
- 其他你在 Store 找到的

> 不同 actor 的**输入字段**（keyword / asin / urls）和**输出字段**（reviewText / content…）不一样。本项目默认按 `compass/listing-amazon-reviews` 的常见字段做了映射（见 `multi_agents/ecommerce/tools/apify_search.py` 的 `_map_item`）。换了 actor 如果结果对不上，改 `_map_item` 和 `payload` 即可。

---

## 4. 配置 .env

在项目根目录 `.env` 里加（**三个变量**）：

```bash
# 1) Apify token（第 2 步拿到的）
APIFY_API_TOKEN=apify_api_xxxxxxxxxxxxxxxxxxxxxxx

# 2) 切换检索源到 apify（不设则默认 tavily）
ECOMMERCE_SEARCH_BACKEND=apify

# 3) 可选：指定 actor（不设用默认 compass/listing-amazon-reviews）
APIFY_REVIEW_ACTOR=compass/listing-amazon-reviews

# 4) 可选：Amazon 站点国家（默认 US）
APIFY_AMAZON_COUNTRY=US
```

> ⚠️ token 是密钥，`.env` 已在 `.gitignore` 里，不会被提交。**不要**把 token 写进代码或文档。

---

## 5. 启用并验证

配好 `.env` 后，正常跑即可，runner 会自动检测 `ECOMMERCE_SEARCH_BACKEND=apify` 并切换：

```bash
# CLI
python -m multi_agents.ecommerce --query "portable blender" --depth standard

# 或前端（启动后端后访问研究页）
python -m uvicorn main:app --port 8000
#   http://localhost:8000/site/ecommerce.html
```

**验证是否生效**：看日志（控制台或 `logs/ecommerce/<时间戳>_<关键词>.log`）：

```
[runner] 检索源: Apify
[apify] query='portable blender reviews' actor=compass/listing-amazon-reviews 返回 8 条
[ReviewInsight] 检索完成 sources=8 原始痛点=6
```

报告「用户痛点」一节会是基于真实 Amazon 评论归纳的中文痛点。

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
| `[apify] 返回 0 条` | actor input 字段名不对（keyword vs searchQueries），或该 actor 不支持关键词搜；查该 actor 文档，改 `apify_search.py` 的 `payload` |
| 结果字段对不上（title/body 空） | actor 输出字段名不同；改 `_map_item` 的字段映射 |
| 超时 / 很慢 | Amazon 评论 actor 跑一次可能几十秒~几分钟；`run-sync` 会等，正常现象 |
| 402 / 额度不足 | Apify 免费额度用完，充值或换免费 actor |

---

## 8. 设计说明

- **注入式**：Apify 实现成一个标准 `SearchFn = async (query, max_results) -> list[dict]`，和 Tavily 接口完全一致。`review_insight` 等 Agent 不关心数据来自哪，只消费标准化后的 source。
- **可降级**：Apify 不可用时自动回退 Tavily，保证流程不崩。
- **可扩展**：以后接 SerpAPI / Rainforest API / 自建爬虫，只要再实现一个 `SearchFn` 并在 `_resolve_search_fn` 里加一个 backend 分支即可。
