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
| portable-blender | 7.1 | 18 | 0 | 0.84 | 通过 |
| pet-water-fountain | 6.5 | 18 | 0 | 0.84 | 通过 |
| standing-desk | 6.82 | 30 | 0 | 0.88 | 通过 |

数据见 `outputs/ecommerce/demo-cases/*/evaluation.json`，可用 `python scripts/export_ecommerce_demo_cases.py` 复现。
全链路日志：`logs/ecommerce/<时间戳>_<关键词>.log`。

## 面试可讲的工程点

- **并发编排**：`asyncio.gather` 三路研究 + 独立子状态，避免共享可变集合在协程间交错。
- **可观测性**：每次研究生成独立 log 文件，记录全链路 `INFO/WARNING/ERROR`；每个 Agent 写 `audit_log`（status / duration_ms / source_count / confidence / warning）。
- **容错**：检索失败 / JSON 异常 / LLM 限流均降级；批量导出时单 case 失败不中断其余 case，manifest 照常写出。
- **可测试**：55 个单测，注入式 `search_fn` / `llm_fn` 解耦网络与 LLM，测试不触网不花钱。
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

## 相关文件

- 设计文档：`docs/superpowers/specs/2026-06-18-ecommerce-research-agent-design.md`
- 实现计划：`docs/superpowers/plans/2026-06-18-ecommerce-research-agent.md`
- 打磨计划：`docs/superpowers/plans/2026-06-18-ecommerce-portfolio-polish-plan.md`
- 使用说明：`docs/ecommerce-researcher.md`
