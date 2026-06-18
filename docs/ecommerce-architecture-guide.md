# EcomResearcher 完整架构与 SOP 详解

> 本文档系统讲解 EcomResearcher（跨境电商 AI 选品与市场调研助手）的整体架构、数据流（SOP）、核心组件与关键机制。
> 面向想读懂这套系统、或在面试中讲清楚它的人。配套：`README.md` / `docs/ecommerce-researcher.md` / `docs/ecommerce-portfolio-notes.md`。

---

## 1. 项目定位

EcomResearcher 是在开源 [GPT Researcher](https://github.com/assafelovic/gpt-researcher) 与 LangGraph 基础上**二次开发**的跨境电商垂直多 Agent 工作流。

输入一个品类关键词（如 `portable blender`），系统自动完成：

- 市场趋势研究
- 竞品格局分析（含价格区间）
- 用户评论痛点洞察（中文化归纳）
- 机会评分（LLM 打分 + 规则兜底）
- 结构化选品报告（固定 10 节 Markdown + 引用）
- 质量检查 + 全链路审计日志

**设计理念**：底座（搜索/抓取/LLM 抽象）复用 GPT Researcher；垂直业务（选品流程、评分体系、质量评估、可观测性）集中在 `multi_agents/ecommerce/` 自研。所有外部依赖（检索器、LLM）以**注入式函数**解耦，保证可测试、可降级。

---

## 2. 技术栈

| 层 | 技术 |
|----|------|
| 编排 | Python asyncio（`asyncio.gather` 并发），LangGraph 风格状态机 |
| Web | FastAPI（REST + WebSocket）、uvicorn |
| 前端 | 原生 HTML/CSS/JS（无构建步骤），Chart.js / marked.js / DOMPurify（CDN） |
| LLM | 任意 OpenAI 兼容模型（DeepSeek / 智谱 GLM / OpenAI），通过 `GenericLLMProvider` |
| 检索 | GPT Researcher 检索器（Tavily / DuckDuckGo / Google ...） |
| 测试 | pytest（asyncio_mode=strict），47 个单测 |
| Python | 3.10+（TypedDict total=False 兼容） |

---

## 3. 整体架构（分层）

```
┌─────────────────────────────────────────────────────────────┐
│  入口层 (Entry)                                              │
│    CLI: python -m multi_agents.ecommerce                     │
│    REST: POST /api/ecommerce/research                        │
│    WS:   /ws/ecommerce (8 段流式进度)                         │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Runner 层 (runner.py)                                       │
│    run_ecommerce_research():                                 │
│      ① create_initial_state  ② 建独立 log 文件               │
│      ③ 调 graph              ④ 写 4 类输出文件 + evaluation   │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Graph 编排层 (graph.py)                                     │
│    run_ecommerce_graph():                                    │
│      planner → [trend ∥ competitor ∥ review] →              │
│      scoring → writer → quality                              │
│      (progress_callback 向外推送阶段事件 + 写 logger)         │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  Agent 层 (agents/)  —— 7 个业务 Agent                       │
│    ProductResearchPlannerAgent (同步)                        │
│    TrendResearchAgent / CompetitorAnalysisAgent /            │
│      ReviewInsightAgent (异步, 并发)                          │
│    OpportunityScoringAgent (异步, LLM 优先)                   │
│    EcommerceReportWriterAgent (同步)                         │
│    QualityReviewerAgent (同步)                               │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  工具/支撑层                                                  │
│    tools/   : source_normalizer / product_search /           │
│               review_extractor / review_scraper(双数据源)    │
│    llm_helper.py : 注入式 LlmFn + JSON 提取 + 降级            │
│    schemas/ : scoring(加权) / report(章节)                    │
│    config.py: fast/standard/deep 三档                        │
│    state.py : EcommerceResearchState (共享状态契约)           │
│    evaluation.py: build_evaluation_summary                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  GPT Researcher 底座 (复用)  │
              │  检索器 / 抓取 / LLM 抽象    │
              └────────────────────────────┘
```

---

## 4. 目录结构

```
multi_agents/ecommerce/
├── __init__.py            # 导出 run_ecommerce_research
├── __main__.py            # CLI 入口 (python -m multi_agents.ecommerce)
├── state.py               # EcommerceResearchState + create_initial_state
├── config.py              # fast/standard/deep 深度档位
├── prompts.py             # 7 个 Agent 的系统提示词(预留 LLM 增强)
├── llm_helper.py          # 注入式 LlmFn + JSON 提取 + clamp + 降级
├── graph.py               # 工作流编排 + 阶段进度回调
├── runner.py              # 端到端入口 + 文件输出 + 按次 log 文件
├── evaluation.py          # 评估摘要 (总分/置信度/证据数/降级数/耗时)
├── agents/
│   ├── planner.py             # 规划: 生成查询 + 评分维度
│   ├── trend_researcher.py    # 趋势研究
│   ├── competitor_analyzer.py # 竞品分析 (含价格抽取)
│   ├── review_insight.py      # 评论痛点 (LLM 中文归纳)
│   ├── opportunity_scorer.py  # 机会评分 (LLM 优先 + 规则兜底)
│   ├── report_writer.py       # 报告生成 (固定 10 节)
│   └── quality_reviewer.py    # 质量检查
├── tools/
│   ├── source_normalizer.py  # 统一数据源格式 + 推断 source_type
│   ├── product_search.py     # 查询构造 + search_sources (注入 search_fn)
│   ├── review_extractor.py   # 关键词抽取痛点句子
│   └── review_scraper.py     # 双数据源评论抓取(Apify两步 + Tavily兜底, 可插拔 ReviewSource)
└── schemas/
    ├── scoring.py           # calculate_overall_score (6 维加权)
    └── report.py            # REPORT_SECTIONS + 标题

backend/server/ecommerce_api.py   # FastAPI 路由 (POST + WS)
frontend/ecommerce.html           # 研究页 (表单+进度+雷达图+报告)
frontend/ecommerce-eval.html      # 评估对比页 (3 case 横向对比)
scripts/export_ecommerce_demo_cases.py  # 标准 demo 导出脚本
tests/test_ecommerce_*.py         # 47 个单测
```

---

## 5. 核心数据结构：EcommerceResearchState

整条流程围绕**一个共享状态**流转（`state.py`）。每个 Agent 只读写自己负责的字段，节点之间不直接传自然语言。

```python
class EcommerceResearchState(TypedDict, total=False):
    # 输入
    query: str                       # 品类关键词
    target_market: str               # 目标市场 (US/UK/...)
    platforms: list[str]             # 平台偏好
    depth: str                       # fast | standard | deep

    # 规划与研究结果
    research_plan: dict              # planner 产出的各类查询 + 评分维度
    trend_result: dict               # 趋势研究 (summary/trend_score/evidence/confidence)
    competitor_result: dict          # 竞品研究 (含 price_range)
    review_result: dict              # 评论研究 (pain_points/pain_points_language)

    # 评分与输出
    opportunity_score: dict          # 6 维分 + overall + recommendation + scored_by
    final_report: str                # 最终 Markdown 报告
    quality_check: dict              # 质检结果

    # 可观测性
    audit_log: list[dict]            # 每个 Agent 的执行记录
    errors: list[dict]               # 错误收集
    output_paths: dict               # 各输出文件路径
```

> 设计要点：`total=False` 兼容 Python 3.10；字段按"谁产出谁写入"划分，避免节点间耦合。

---

## 6. SOP 完整流程（端到端）

以一次 `python -m multi_agents.ecommerce --query "portable blender" --depth standard` 为例：

### Step 0：入口与初始化（`__main__.py` → `runner.py`）
1. `load_dotenv()` 加载 `.env`（检索 key、LLM 配置）
2. 解析参数 → 调 `run_ecommerce_research(query=..., llm_fn=default_llm_fn)`
3. `create_initial_state()` 构造初始 state
4. `_setup_run_log()` 创建**独立日志文件** `logs/ecommerce/<时间戳>_<关键词>.log`，绑定到 `multi_agents.ecommerce` logger

### Step 1：规划（`agents/planner.py`，同步）
- 输入：`query / target_market / depth`
- 用 `build_ecommerce_queries()` 按四种意图（trend/competitor/review/risk）生成查询模板，按深度档位截断
- 输出 `research_plan`：
  ```python
  {
    "trend_queries": ["portable blender market trend US", ...],
    "competitor_queries": ["portable blender amazon best sellers", ...],
    "review_queries": ["portable blender customer complaints", ...],
    "risk_focus": [...],
    "scoring_dimensions": ["trend_score", "competition_score", ...]
  }
  ```
- 写一条 `audit_log`（duration_ms / status）

### Step 2：三路并发研究（`graph.py` + 三个研究 Agent，异步）
`asyncio.gather` 同时启动三个研究节点。每个节点拿到 `_make_child_state(state)` 构造的**独立子状态**（独立 `audit_log` / `errors`，避免并发写共享集合）。

每个研究节点的内部 SOP（以 `TrendResearchAgent` 为例）：
1. 从 `research_plan` 取自己的 queries
2. `search_sources()`：逐条 query 调注入的 `search_fn` → `normalize_source` 统一格式 → 按 url 去重 → 截断到 `max_sources_per_agent`
3. 产出结果（summary / score / key_findings / evidence / confidence）
4. **失败降级**：检索异常或数据不足 → 走 fallback（低置信度、低分），写 `audit_log`（status=partial + warning），**不抛异常中断**
5. `ReviewInsightAgent` 走**双数据源评论抓取**（见 8.4）：`get_review_scraper()` 选源——有 `APIFY_API_TOKEN` 时 Apify 抓 Amazon 真实评论（两步：关键词→ASIN→评论），失败/无 token 自动降级 Tavily 搜网页抽评论句；拿到评论后 LLM 归纳为**中文痛点**（`pain_points_language=zh`），不可用保留原文。audit 记录 `review_source/review_count/platforms/fallback_reason`
6. trend/competitor 的 summary 也是 **LLM 基于真实检索资料生成**（`summary_source=llm`），失败回退模板（`summary_source=template`）

并发结束后，`graph` 合并三方 `*_result` + 各自 `audit_log` / `errors` 回主 state。

### Step 3：机会评分（`agents/opportunity_scorer.py`，异步）
- 汇总 trend/competitor/review 三方结果
- **LLM 优先**：若 `llm_fn` 可用，让 LLM 对趋势/竞争/痛点/利润/风险五维打分并给中文理由（要求 JSON 输出）
- **规则兜底**：LLM 不可用 / JSON 解析失败 / 字段异常 → 回退规则基线分
- `evidence_score` 始终按证据数量客观计算（不交给 LLM）
- `overall_score` 由 `calculate_overall_score()` 按固定权重重算（保证口径一致、可解释）
- 记录 `scored_by: "llm" | "rule"` 便于审计

### Step 4：报告生成（`agents/report_writer.py`，同步）
- 按 `REPORT_SECTIONS` 固定 10 节拼 Markdown：
  1. 选品结论 / 2. 市场趋势 / 3. 竞品格局 / 4. 用户痛点 / 5. 差异化机会 /
  6. 价格与利润 / 7. 风险因素 / 8. 机会评分(含评分方式+理由) / 9. 是否建议进入 / 10. 引用
- 引用来自三方 `evidence` 的 url，去重编号
- 第 7 节强制含「风险」与「销量预测」字样（供质检验证风险披露）

### Step 5：质量检查（`agents/quality_reviewer.py`，同步）
对最终报告做多维质检：
- `citation_coverage`：报告含 http(s) 引用数 / 基准
- `evidence_sufficiency`：三方 evidence 总数 / 基准
- `risk_disclosure`：是否同时含「风险」+「销量预测」
- **过度确定性**：扫描「稳赚/必爆/一定增长/没有风险/保证成功」等表述
- 产出 `passed` + `issues` 列表

### Step 6：写文件 + 评估摘要（`runner.py`）
- `report.md` / `audit.json` / `quality.json` / `evaluation.json`
- `build_evaluation_summary()` 浓缩为可比较指标：总分/置信度/证据数/降级数/耗时/评分方式/质检
- `_teardown_run_log()` 关闭日志 handler
- 返回 `final_state`（含 `evaluation_summary` + `output_paths`）

**整个流程的每个阶段**都会通过 `progress_callback` 向外推送事件（`start → planner_done → research_running → research_done → scoring_done → report_done → quality_done → done`），同时写入按次 log 文件。

---

## 7. 七个 Agent 详解

| Agent | 同步/异步 | 职责 | 输出字段 | 降级策略 |
|-------|-----------|------|----------|----------|
| **ProductResearchPlannerAgent** | 同步 | 拆解品类为四类查询 + 评分维度 | `research_plan` | 纯模板，无外部依赖，不降级 |
| **TrendResearchAgent** | 异步 | 市场趋势/热度/季节性 | `trend_result` (trend_score/evidence/confidence) | 检索失败→低置信度低分 |
| **CompetitorAnalysisAgent** | 异步 | 竞品/价格区间/卖点/竞争强度 | `competitor_result` (price_range) | 同上；价格用正则抽 `$N` |
| **ReviewInsightAgent** | 异步 | 评论痛点（LLM 中文归纳） | `review_result` (pain_points/language) | LLM 失败→保留英文原文 |
| **OpportunityScoringAgent** | 异步 | 机会评分（LLM 优先） | `opportunity_score` (6 维+overall+scored_by) | LLM 失败→规则基线 |
| **EcommerceReportWriterAgent** | 同步 | 固定 10 节 Markdown + 引用 | `final_report` | 纯模板拼装，不降级 |
| **QualityReviewerAgent** | 同步 | 引用/证据/风险/过度确定性 | `quality_check` | 纯规则检查，不降级 |

---

## 8. 关键机制

### 8.1 并发编排（asyncio.gather + 独立子状态）
三个研究节点用 `asyncio.gather` 并发。为避免三个协程并发写同一个 `audit_log` 列表导致交错，`graph._make_child_state()` 给每个节点一份**独立子状态**（独立空 `audit_log` / `errors`，只读字段共享），并发结束后由 graph 统一合并。

### 8.2 注入式依赖（search_fn / llm_fn）
- `SearchFn = async (query, max_results) -> list[dict]`：检索器抽象。生产用 `default_search_fn`（复用 GPT Researcher 默认检索器，`asyncio.to_thread` 包同步调用实现真并发）；测试用 `fake_search`（不触网）。
- `LlmFn = async (system, user) -> str`：LLM 抽象。生产用 `default_llm_fn`（复用 SMART_LLM 配置）；测试用 `fake_llm`。
- 好处：核心逻辑与外部服务解耦，测试快、不花钱、可重复。

### 8.3 LLM 打分 + 规则降级（`opportunity_scorer.py`）
```
LLM 可用 & JSON 合法 → 用 LLM 五维分 + 理由 (scored_by=llm)
        ↓ 否则
LLM 不可用 / 解析失败 / 字段异常 → 规则基线分 (scored_by=rule)
        ↓ 始终
evidence_score 按证据数算；overall 按固定权重重算
```
`_score_from_llm()` 逐字段容错（null/坏字符串→回退该字段规则值），保证部分字段坏不会整体崩。

### 8.4 双数据源评论抓取（`review_insight.py` + `tools/review_scraper.py`）
评论走可插拔双数据源（统一接口 `ReviewSource.scrape(query, platforms, max_reviews)`）：
- **Apify 真实评论**（有 `APIFY_API_TOKEN`）：Amazon **两步**——关键词搜产品拿 ASIN（`igview-owner~amazon-search-scraper`）→ ASIN 抓评论（`web_wanderer~amazon-reviews-extractor`），返回结构化 `ReviewItem`（rating/date/helpful/product_url）
- **Tavily 兜底**（无 token / Apify 失败）：搜含评论的网页 → 抽取评论句包成 `ReviewItem`（platform=web）
- 工厂 `get_review_scraper()` 自动选源；Apify 运行时失败/返回空 → review_insight 捕获后切 Fallback（`fallback_reason` 记录原因）
- 拿到评论后统一 LLM 归纳中文痛点（`pain_points_language=zh`），LLM 不可用保留原文，绝不中断
- actorId 用 `~` 格式（`/` 在 run-sync 端点会 404）；Reddit/TikTok/Google Maps 接口已预留，加 actor 即扩展
- 真实测试：free plan 第一步（关键词→ASIN）通，第二步评论抓不到（需 Apify 付费 proxy），但**降级完美工作**（见 `docs/ecommerce-apify-setup.md`）

### 8.5 失败降级（四层）
| 层 | 失败场景 | 降级 |
|----|----------|------|
| 检索 | Tavily 限流/网络 | 返回空结果，agent 走低置信度 |
| JSON | LLM 返回非合法 JSON | `extract_json` 提取，失败则规则兜底 |
| LLM | 调用异常/额度不足 | `llm_json` 吞异常返回 (None, False)，上层规则降级 |
| 批量 | 单个 demo case 抛错 | `export` 脚本 per-case try/except，错误 case 进 manifest 但不中断其余 |

### 8.6 审计日志（audit_log）
每个 Agent 结束写一条：`{agent, status(success/partial), duration_ms, source_count, confidence, warning}`。端到端可追溯。

### 8.7 质量评估（quality_check）
引用覆盖率 / 证据充分度 / 逻辑一致性(基线) / 风险披露 / 过度确定性拦截。`passed` + `issues` 暴露问题。

### 8.8 全链路日志文件
每次研究在 `logs/ecommerce/<时间戳>_<关键词>.log` 写独立 log，绑定 `multi_agents.ecommerce` logger，捕获 graph 阶段 / 各 Agent / LLM 调用失败的 INFO/WARNING/ERROR。事后排查友好。

---

## 9. 深度档位（config.py）

| depth | max_queries_per_agent | max_sources_per_agent | 适用 |
|-------|----------------------|----------------------|------|
| fast | 2 | 3 | 快速预览（~30-60s） |
| standard | 4 | 6 | 默认 |
| deep | 6 | 10 | 更完整（更慢） |

未知 depth 自动回退 standard。

---

## 10. 接口层

### 10.1 CLI
```bash
python -m multi_agents.ecommerce --query "portable blender" --market US --depth standard
# --no-llm 可禁用 LLM（纯规则，不消耗额度）
```

### 10.2 FastAPI（`backend/server/ecommerce_api.py`，独立 APIRouter）
- `POST /api/ecommerce/research`：请求体 `{query, target_market, platforms, depth, use_llm}`，同步返回 `report / opportunity_score / quality_check / audit_log / evaluation_summary / output_paths`。
- `WS /ws/ecommerce`：发 `{query,...}` → 逐阶段推送 8 个事件 → `done` 回传完整结果。

### 10.3 前端
- 研究页 `http://localhost:8000/site/ecommerce.html`：表单 → WebSocket 进度时间线 → 评分雷达图 → 质检 → Agent 链路表 → Markdown 报告。
- 评估对比页 `http://localhost:8000/site/ecommerce-eval.html`：读 `case-index.json`，三 case 横向对比（总分/置信度/证据/降级/耗时 + quality badge + 评分条）。

---

## 11. 评估层（evaluation.py）

`build_evaluation_summary(state)` 把一次研究浓缩为可比较指标：

```python
{
  "overall_score": 7.1,
  "confidence": 0.84,        # 研究节点平均置信度(排除质检)
  "evidence_count": 18,      # 三方证据总数
  "fallback_count": 0,       # 非 success 的 agent 数
  "duration_ms": 42000,
  "recommendation": "...",
  "scored_by": "llm",
  "quality_passed": true,
  "review_source": "apify",   # apify | web_fallback（评论来自哪）
  "review_count": 12          # 抓到的评论数
}
```
供 runner 写 `evaluation.json`、demo 导出、评估对比页统一消费。

---

## 11.5 运行时治理层（Runtime Governance）

> 治理层「包」在 Agent 图的外围，而非塞进某个 Agent 内部。四个职责模块协同：

| 模块 | 职责 | 落点 |
|------|------|------|
| `PolicyGuard` | 执行前校验请求（query / depth / market / platforms）、Agent 级工具权限、不安全 URL 过滤（file / loopback / 私网）、密钥脱敏 | `runtime/policy_guard.py`，runner 入口 + source_normalizer |
| `BudgetManager` | 执行中按 LLM / search / scrape / external_api 配额计费，超额自动降级（如 LLM 预算耗尽 → 规则评分） | `runtime/budget_manager.py`，scoring / search / scraper |
| `ExecutionGuard` | 包裹高风险调用，提供 timeout / retry / fallback，记录每次重试与降级事件 | `runtime/execution_guard.py` |
| Telemetry | `record_event` / `summarize_governance` 把上述事件合并进 `state["governance"]` → audit_log → evaluation_summary | `runtime/telemetry.py` |

**关键设计**：`graph._make_child_state` 让并发子状态**共享**主状态的 `governance` dict 引用（trend / competitor / review 的结果字段仍各自独立），因此 review 分支在子状态里记录的降级事件能无损回流到主状态，最终进入 `evaluation.json` 与评估对比页（重试 / 策略拦截 / LLM·Search 调用等列）。

**生产接入点**：

- `run_ecommerce_graph()` 用 `ExecutionGuard` 包裹 trend / competitor / review 三个并发研究节点；单个节点异常会记录 governance failure，并转成 partial 子状态继续合并，避免整条工作流直接中断。
- `make_budgeted_search_fn()` 在 Trend / Competitor / Review 三个 Agent 各自的 search 调用前执行工具权限检查与 search 预算检查；超预算会记录 budget degradation 并返回空结果。
- `ApifyReviewScraper` 在 Amazon product search / review fetch 两类 `requests.post` 前检查 `external_api` 预算；预算耗尽时不会发出外部 API 请求，而是返回空结果交给 ReviewInsightAgent 降级 Tavily。
- `ExecutionGuard` 写入 governance error event 前会通过 `PolicyGuard.redact_secrets()` 对 `TOKEN=...` / `api_key=...` / `password=...` 等错误消息做脱敏。

预算阈值可通过环境变量 `ECOMMERCE_MAX_LLM_CALLS` / `ECOMMERCE_MAX_SEARCH_CALLS` / `ECOMMERCE_MAX_SCRAPE_CALLS` / `ECOMMERCE_MAX_EXTERNAL_API_CALLS` / `ECOMMERCE_MAX_ESTIMATED_COST_USD` 覆盖（见 `config.get_budget_config()`）。

---

## 12. 可观测性总结

| 维度 | 载体 |
|------|------|
| 阶段进度（实时） | WebSocket 8 段事件 |
| 节点执行（事后） | `audit.json`（每 agent 一条） |
| 质量结果 | `quality.json` |
| 综合指标 | `evaluation.json` |
| 全链路日志 | `logs/ecommerce/<时间戳>_<关键词>.log` |
| 评分来源 | `scored_by` 字段（llm/rule） |

---

## 13. 配置（.env）

```
TAVILY_API_KEY=...                     # 默认检索器
OPENAI_API_KEY=...                     # LLM key
OPENAI_BASE_URL=https://api.deepseek.com   # OpenAI 兼容端点
SMART_LLM=openai:deepseek-v4-flash     # 评分用模型 (provider:model)
FAST_LLM=...  STRATEGIC_LLM=...        # 其他档位
```
> `provider:model` 格式：`openai:` 走 OpenAI 兼容协议（可接 DeepSeek/智谱等）；Config 自动解析。

---

## 14. 运行方式速查

```bash
# 1) CLI 单次
python -m multi_agents.ecommerce --query "portable blender" --depth standard

# 2) 程序化调用
python -c "import asyncio; from multi_agents.ecommerce import run_ecommerce_research; \
  print(asyncio.run(run_ecommerce_research(query='portable blender', depth='standard'))['final_report'][:200])"

# 3) 全栈 (API + 前端)
python -m uvicorn main:app --port 8000
#   浏览器: http://localhost:8000/site/ecommerce.html
#   评估页: http://localhost:8000/site/ecommerce-eval.html

# 4) 导出标准 demo case (3 个)
python scripts/export_ecommerce_demo_cases.py --output-root outputs/ecommerce/demo-cases

# 5) 测试
python -m pytest tests/test_ecommerce_state.py tests/test_ecommerce_tools.py \
  tests/test_ecommerce_agents.py tests/test_ecommerce_runner.py tests/test_ecommerce_evaluation.py -v
```

---

## 15. 扩展点

- **双数据源（已实现）**：Tavily 广域检索 + Apify 平台评论（Amazon 两步、Reddit/TikTok/GMaps 接口预留），无 token 或 Apify 失败自动降级 Tavily
- **新评论平台**：实现一个 `ReviewSource`（如 TikTok/Google Maps scraper）加进 `DEFAULT_ACTORS` 即可
- **Apify 真实评论抓取**：free plan 抓不到 Amazon 评论正文（需付费 residential proxy / Pay-Per-Result actor），token 不变即可生效
- **新垂直领域**：复制 `ecommerce/` 结构改 prompt/评分维度（如 AI 工具调研）
- **持久化**：目前文件存储，可接数据库
- **更多质检维度**：logic_consistency 目前是基线，可接 LLM 交叉校验

---

## 16. 诚信边界

- ✅ 可说：在开源 GPT Researcher 上「二次开发 / 垂直化改造 / 扩展多 Agent 工作流」「设计实现了 `multi_agents/ecommerce/`」
- ❌ 不可说：「从零自研整个研究系统」（底座是开源的）
- 底座（`gpt_researcher/` 的搜索/抓取/LLM 抽象）复用自 GPT Researcher；`multi_agents/ecommerce/`、`backend/server/ecommerce_api.py`、`frontend/ecommerce*.html`、`scripts/export_ecommerce_demo_cases.py` 为自研。
