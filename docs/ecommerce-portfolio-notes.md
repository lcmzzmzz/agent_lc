# EcomResearcher 简历素材

> 汇总可直接用于简历/面试的表述、量化指标与诚信边界。
> 配套：`README.md` / `docs/ecommerce-researcher.md` / `outputs/ecommerce/demo-cases/` / `frontend/ecommerce-eval.html`。

## 一句话定位

基于开源 GPT Researcher 与 LangGraph 二次开发的跨境电商选品垂直多 Agent 工作流。

## 简历要点（Resume bullets）

- 在开源 GPT Researcher 上二次开发跨境电商选品多 Agent 系统，用 LangGraph 编排趋势 / 竞品 / 评论三路并发研究与评分、写作、质检，实现品类输入到结构化报告的自动化闭环。
- 设计 LLM 结构化打分 + 规则降级兜底机制（注入式 `llm_fn`，JSON 解析失败 / 调用异常自动回退规则），保证评分可用性与可解释性。
- 用 FastAPI + WebSocket 实现研究进度流式推送（8 段阶段事件），前端含评分雷达图与 Agent 执行链路可视化。
- 引入审计日志与质量评估（引用覆盖率 / 证据充分度 / 风险披露 / 过度确定性拦截），并做失败降级，提升长链路多 Agent 任务的稳定性与可观测性。
- 设计 Tavily + Apify 双数据源架构：Tavily 负责开放网页检索（趋势 / 竞品 / 评测 / 风险），Apify 负责平台级真实评论抓取（Amazon / Reddit），评论洞察从「摘要检索」升级为「真实用户反馈分析」，并通过可插拔 Scraper + 自动降级保证无 token 时演示仍可跑。
- 标准化 3 个 demo case + 评估对比页，支持可重复导出与横向比较（总分 / 置信度 / 证据数 / 降级数 / 耗时）。

## 可量化指标（真实运行，见 demo case）

| Case | 总分 | 证据数 | 降级数 | 置信度 | 质检 |
|------|------|--------|--------|--------|------|
| portable-blender | 6.92 | 18 | 0 | 0.88 | 通过 |
| pet-water-fountain | 7.62 | 18 | 0 | 0.88 | 通过 |
| standing-desk | 6.76 | 25 | 0 | 0.85 | 通过 |

数据见 `outputs/ecommerce/demo-cases/*/evaluation.json`，可用 `python scripts/export_ecommerce_demo_cases.py` 复现。
全链路日志：`logs/ecommerce/<时间戳>_<关键词>.log`。
三个 case 均走 Tavily（`review_source=web_fallback`）；evaluation.json 还含 governance 字段（llm/search 调用数、estimated_cost、降级/失败计数）。

## 面试可讲的工程点

- **并发编排**：LangGraph `StateGraph` fork-join（`planner→{trend,competitor,review}→scoring`），由图原生并发执行；`Annotated[list, operator.add]` reducer 自动合并三分支的 audit_log/errors，governance 靠闭包共享同一 dict（不走 channel，避免并发写冲突）。
- **可观测性**：每次研究生成独立 log 文件，记录全链路 `INFO/WARNING/ERROR`；每个 Agent 写 `audit_log`（status / duration_ms / source_count / confidence / warning）。
- **容错**：检索失败 / JSON 异常 / LLM 限流均降级；批量导出时单 case 失败不中断其余 case，manifest 照常写出。
- **可测试**：86 个单测（含字段名真因回归测试），注入式 `search_fn` / `llm_fn` 解耦网络与 LLM，测试不触网不花钱。
- **中文化**：评论痛点由 LLM 从英文资料归纳为中文（`pain_points_language=zh`），LLM 不可用时保留原文并标注。

## 诚信边界（重要）

- ✅ 可说：在开源项目上「二次开发 / 垂直化改造 / 扩展多 Agent 工作流」「设计并实现了 `multi_agents/ecommerce/` 选品模块」。
- ❌ 不可说：「从零自研整个研究系统」（底座 GPT Researcher 是开源的）。
- 底座的搜索 / 抓取 / LLM 抽象（`gpt_researcher/`）复用自 GPT Researcher；`multi_agents/ecommerce/`、`backend/server/ecommerce_api.py`、`frontend/ecommerce*.html`、`scripts/export_ecommerce_demo_cases.py` 为本次新增自研代码。

## 调试故事：评论数据源相关性 bug（面试加分项）

真实联调时发现：调研「蓝牙音箱」，生成的「用户痛点」全是三星手机内容（隐私屏幕 / S Pen / 摄像头模组）。

**定位过程**（体现排障能力）：
1. 看 `logs/ecommerce/<时间戳>_蓝牙音箱.log`，发现评论走的是真实 Apify（`review_source=apify`），第二步抓到 120 条评论——说明数据源在跑，但内容是错的。
2. 抓第一步返回的 5 个 ASIN 的真实商品页，确认 `B0G4SW96R4`=三星 S26、`B0FXY18C1J`=三星 A17——**搜音箱返回的全是手机**。
3. 根因：Apify `amazon-search-scraper` 在免费额度下对中文 keyword 行为异常，返回默认热门商品；而原代码只取了 ASIN、没有产品相关性校验，错误产品一路传到了评论归纳。LLM 没有错——喂它手机评论它就老实归纳手机的痛点，看起来毫无破绽。

**修复**（体现工程严谨 + 容错设计）：
- `_search_asins` → `_search_products`：返回带 `title` 的产品，title 用于校验。
- `_filter_relevant_products`：基于**品类核心词**校验。关键细节——`bluetooth/wireless/portable` 这类通用修饰词几乎所有电子产品标题都有（手机也带 bluetooth），拿它们判相关性会把「手机冒充音箱」误判为相关；必须过滤掉，只认 `speaker/blender` 这种品类词，才能挡住跑偏。
- `_to_search_keyword`：LLM 把中文 query 翻成英文 Amazon keyword（蓝牙音箱→bluetooth speaker），提高命中率且英文可校验。
- 校验不过 → 返回空 → 复用既有降级链路自动切 Tavily。**宁可降级给 Tavily（音箱相关），也绝不拿错误产品冒充音箱。**

**验证**：真实重跑蓝牙音箱，日志显示「相关性校验未通过 → 降级 Tavily」，痛点从手机变成音箱（电池续航虚标 / 退货流程）。单测 47→55，新增 8 个覆盖相关性校验 + keyword 翻译 + 降级链路。

**面试金句**：「数据源相关性是 LLM 应用容易翻车的隐性 bug——模型很诚实，你喂它手机的评论它就归纳手机的痛点，结果看起来毫无破绽。解法是在数据进入模型前加一层相关性闸门 + 优雅降级，而不是信任上游数据源。」

---

### 真因复盘（2026-06-18 二次排查）—— 第一轮的根因判断其实是错的

第一轮把现象归因为「Apify free actor 对中文 keyword 行为异常返回默认商品」。后来发现 Apify 评论路径**始终走不通**（每次都降级 Tavily），重新排查才挖到真因——**两个字段名 bug 叠加**：

1. **input 字段名错配**：代码传 `{"keyword", "maxResults"}`，actor 实际认 `{"query", "maxPages"}`（查 Apify store 文档 + 实跑 dump 返回确认）。actor 收到不认识的字段 → 退化成默认搜索 `"Smart Phone"` → 永远返回三星手机。**跟中英文无关**，传任何词都返回手机。
2. **返回字段名错配**：actor 返回的产品名字段叫 `product_title`，代码却读 `title`/`name`/`productName`（三个全 miss）→ title 恒空。

两层叠加产生一个极具迷惑性的现象：第一轮加的相关性校验，因为 **title 恒空**，把所有产品都 `if not title: continue` 跳过 → `相关产品数=0` → 触发降级。**降级结果是对的（产品确实是手机，该降级），但触发机制是错的**——不是因为校验挡住了手机，而是因为 title 空全 skip。这是「**结果对掩盖根因错**」的典型隐性 bug。

**真修复**：input 改 `query/maxPages/country`，返回改 `product_title` 优先 + 兜底。实跑验证：`bluetooth speaker` 真返回 Anker Soundcore 2 / JBL FLIP 5，`headphones` 返回 Sony / Apple，不再是手机；顺带白捡 `sales_volume`（"10K+ bought in past month"）/ `product_star_rating` / `is_amazon_choice` 等 Amazon 选品金矿字段。单测 19（review_scraper）+ 全 ecommerce 86 全绿，新增字段映射回归测试。

> 端到端「抓到真实评论」受 Apify 月度额度耗尽限制未当场跑通（错误体 `Monthly usage hard limit exceeded`），与代码无关；修复正确性已由真实 search 返回 + 单测证明，额度恢复即可跑通。

**升级金句**：「这个 bug 最坑的不是字段名错了，而是第一轮修复看起来生效了（降级了、报告也对了），根因判断却完全错误、被『结果正确』掩盖。数据源集成的隐性 bug 就这样——你加的防御机制可能误打误撞 cover 住症状，却把真正的字段名错配藏得更深。排查不能停在『现象消失』，要追到『每一层为什么这样行为』。教训：对接第三方 API 第一守则核对真实 schema 字段名，不能凭名字猜，更不能信 actor 的 example（它的 `exampleRunInput` 竟然是 `{"helloWorld": 123}`）。」

## 相关文件

- 设计文档：`docs/superpowers/specs/2026-06-18-ecommerce-research-agent-design.md`
- 实现计划：`docs/superpowers/plans/2026-06-18-ecommerce-research-agent.md`
- 打磨计划：`docs/superpowers/plans/2026-06-18-ecommerce-portfolio-polish-plan.md`
- 使用说明：`docs/ecommerce-researcher.md`
