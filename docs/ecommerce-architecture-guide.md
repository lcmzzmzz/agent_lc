# EcomResearcher 完整架构与 SOP 详解

> 本文档系统讲解 EcomResearcher（跨境电商 AI 选品与市场调研助手）的整体架构、数据流（SOP）、核心组件与关键机制。
> 面向想读懂这套系统、或在面试中讲清楚它的人。配套：`README.md` / `docs/ecommerce-researcher.md` / `docs/ecommerce-portfolio-notes.md`。
>
> **想学源码？先读下一节「§0 源码阅读指南」**——它给出推荐阅读顺序、每个文件的关键设计点、动手验证清单，以及面试深问的 5 个「为什么」。其余章节是按主题组织的参考手册。

---

## 0. 源码阅读指南（先读这一节）

这份文档既是架构参考、也是源码导览。建议**从外到内、从简到繁**读代码，每读完一层能回答一个核心问题。读完一定要动手跑（见末尾清单）。

### 推荐阅读顺序

**① 抓骨架（state → runner，~30 分钟）**
- `state.py`：整条流程的**共享契约**。先读 `EcommerceResearchState`（每个字段谁写谁读，见 §5）+ `create_initial_state()` + `EcommerceGraphState`（langgraph 的 `Annotated[list, operator.add]` reducer 怎么合并并发分支）。
- `runner.py::run_ecommerce_research`：端到端入口。6 步：建 state → 建独立 log → 跑 graph → 写 4 类文件 → 写 evaluation → 返回。
- _读完能回答：一次研究从命令行到报告文件，数据怎么流的？_

**② 啃编排核心（`graph.py`，项目设计的心脏，~45 分钟）**
- `build_ecommerce_graph()` 构建 + compile langgraph StateGraph。边读边想清楚 4 个「为什么」（这是面试最该讲的）：
  - **拓扑** `planner→{trend,competitor,review}→scoring→writer→quality`（§8.1）：为什么用图的 fork-join 而非 `asyncio.gather`？
  - **`_fresh_child()` + 节点返回增量**：为什么在全新 `[]` 上 append、只返回增量？（reducer 会把全量再 add 一遍 → 重复累加）
  - **`governance = state["governance"]` 闭包共享、不进 channel**：为什么不放 state channel？（plain channel 并发写触发 `InvalidUpdateError`）
  - **`_research_node` 用 bare name 调 `run_*`**：为什么不用闭包绑定？（支持测试 `monkeypatch.setattr`）
- _读完能回答：三路怎么并发？audit_log 怎么合并？governance 怎么不冲突？_

**③ 读 7 个 Agent（按「纯计算 → 有降级 → 最复杂」，1-2 小时）**
1. `planner.py`（最简，同步模板）：看 `finalize_audit()` 怎么写审计。
2. `report_writer.py` / `quality_reviewer.py`（同步拼装/检查）：报告 10 节结构 + 质检维度。
3. `trend_researcher.py` / `competitor_analyzer.py`（异步，try/except 降级）：**这两个几乎逐行同构**，读一个就懂另一个。看 try/except 怎么把失败软化成 partial。
4. `opportunity_scorer.py`（LLM 优先 + 规则兜底）：`_score_from_llm` 逐字段容错、confidence 折扣（LLM 降级时 ×0.8）。
5. `review_insight.py`（最复杂）：Apify→Tavily **双源换源重试** + LLM 中文归纳。这是唯一不该被装饰器统一的业务逻辑。
- 共性：7 个 agent 结束都调 `agents/audit.py::finalize_audit()` 统一写审计（§8.6）。
- _读完能回答：每个 agent 失败了怎么办？降级为什么有 3 套而非 1 套？_

**④ 支撑层（tools / runtime / llm_helper / schemas，~45 分钟）**
- `tools/review_scraper.py` 重点：`_search_products`（字段名 `query`/`maxPages`/`product_title`——**真实踩坑修出来的**，见 portfolio 调试故事）、`_filter_relevant_products`（挡「搜音箱返回手机」）、双源降级。
- `runtime/` 治理四件套（§11.5）：`policy_guard`（SSRF 防护 + 密钥脱敏）、`budget_manager`（配额计费降级）、`execution_guard`（timeout/retry/fallback）、`telemetry`（事件聚合）。
- `llm_helper.py`：注入式 `LlmFn` + `llm_json`/`llm_text`（失败软降级）+ `clamp`。
- `schemas/`：`scoring`（6 维加权）、`report`（章节）。
- _读完能回答：外部依赖怎么解耦？失败怎么不崩？成本/安全怎么治理？_

**⑤ 接口与验证（~30 分钟）**
- `backend/server/ecommerce_api.py`（REST + WS，独立 APIRouter）、`frontend/ecommerce*.html`。
- `tests/test_ecommerce_*.py`（**87 个——测试是最好的文档**）：每个 agent 的 happy path + 降级路径都有单测。尤其 `test_ecommerce_graph_langgraph.py` 是 langgraph 迁移的物证（拓扑/并发/reducer/governance 契约）。

### 动手验证清单（边读边做）
1. **跑一次**：`python -m multi_agents.ecommerce --query "portable blender"`，看 `outputs/ecommerce/*-report.md` + `logs/ecommerce/*.log`。
2. **读日志**：按阶段 `[graph] start → planner_done → research_running → ...`，对照源码看每行从哪来。
3. **改阈值**（如 trend 的 `source_count>=2` → `>=5`）跑测试看哪些挂，理解字段依赖。
4. **`--no-llm` 跑一次**，对比 `evaluation.json` 的 `scored_by=rule` + confidence（LLM 降级打折后的值）。
5. **跑 langgraph 物证测试**：`python -m pytest tests/test_ecommerce_graph_langgraph.py -v`。

### 面试深问的 5 个「为什么」（读代码时想清楚）
1. **governance 走闭包不走 channel**（`graph.py:112`）→ 并发写冲突
2. **节点返回增量非全量**（`_fresh_child`）→ 否则 reducer 双计
3. **降级 3 套不统一**（try/except / 双源换源 / 软降级）→ 业务逻辑各异，硬统一风险高（见 §8.5）
4. **audit 用 `finalize_audit` 统一**（`agents/audit.py`）→ 字段一致、防漏抄
5. **第三方 API 字段名要实跑验证**（`review_scraper` 的 query/maxPages/product_title）→ 静默失败比报错更危险

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
| 编排 | LangGraph `StateGraph`（`START→planner→{trend,competitor,review}` fork-join `→scoring→writer→quality→END`，`Annotated[list,operator.add]` reducer 合并并发分支） |
| Web | FastAPI（REST + WebSocket）、uvicorn |
| 前端 | 原生 HTML/CSS/JS（无构建步骤），Chart.js / marked.js / DOMPurify（CDN） |
| LLM | 任意 OpenAI 兼容模型（DeepSeek / 智谱 GLM / OpenAI），通过 `GenericLLMProvider` |
| 检索 | GPT Researcher 检索器（Tavily / DuckDuckGo / Google ...） |
| 测试 | pytest（asyncio_mode=strict），87 个单测 |
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
│  Graph 编排层 (graph.py —— 真正的 LangGraph StateGraph)      │
│    build_ecommerce_graph() → compiled graph                  │
│      START→planner→{trend∥competitor∥review}→scoring        │
│      →writer→quality→END  (fork-join 由图原生并发)            │
│      audit_log/errors: Annotated reducer 自动合并三分支       │
│      governance: 闭包共享同一 dict(不走 channel)              │
│      (progress_callback 闭包推送阶段事件 + 写 logger)         │
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
tests/test_ecommerce_*.py         # 87 个单测
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
LangGraph StateGraph 的 fork-join 同时启动三个研究节点。每个节点在**全新的 `audit_log` / `errors`** 上 append、只返回增量，由 `Annotated[list, operator.add]` reducer 自动拼接（避免并发写共享集合）。

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
- 第 7 节列通用方法论风险（数据不完整/样本偏差/成本未验证）；质检的 risk_disclosure 改为基于真实差评痛点判定（不再靠字面"风险"二字，避免循环论证）

### Step 5：质量检查（`agents/quality_reviewer.py`，同步）
对最终报告做多维质检：
- `citation_coverage`：报告含 http(s) 引用数 / 基准
- `evidence_sufficiency`：三方 evidence 总数 / 基准
- `risk_disclosure`：基于真实差评痛点（`pain_points` 非空）判定；无痛点数据则提示披露不足
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

### 8.1 并发编排（LangGraph StateGraph fork-join + reducer）
三个研究节点是图里的三条 fan-out 边（`planner→trend/competitor/review`），由 langgraph 在一个 superstep 内并发执行，`scoring` 节点自动 barrier 等三者完成。为避免并发写同一个 `audit_log` 列表导致冲突，每个节点在**全新空** `audit_log`/`errors` 上 append、只返回增量，由 `EcommerceGraphState` 的 `Annotated[list, operator.add]` reducer 自动拼接。`governance` 不走图 channel（plain channel 并发写会触发 `InvalidUpdateError`），改由 `build_ecommerce_graph` 闭包捕获同一 dict 引用原地修改。

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
每个 Agent 结束统一调 `agents/audit.py::finalize_audit()` 写一条基线 6 字段（`{agent, status, duration_ms, source_count, confidence, warning}`）；ReviewInsightAgent 额外透传 `review_source/search_keyword/review_count/platforms/fallback_reason`。端到端可追溯，字段一致防漏抄（原本散在 7 个文件手写）。

### 8.7 质量评估（quality_check）
引用覆盖率 / 证据充分度 / 逻辑一致性(基线) / 风险披露 / 过度确定性拦截。`passed` + `issues` 暴露问题。

### 8.8 全链路日志文件（Python logging 落地 runner.py）

每次研究在 `logs/ecommerce/<时间戳>_<关键词>.log` 写独立 log，绑定 `multi_agents.ecommerce` logger，捕获 graph 阶段 / 各 Agent / LLM 调用失败的 INFO/WARNING/ERROR。事后排查友好。实现见 `runner.py::_setup_run_log` / `_teardown_run_log`，原理是 Python 标准 `logging` 模块。

#### 四角色：一条日志的旅程

```
代码 logger.info("xxx")
   → Logger（发言人）
       → 闸① Logger 自己的 level
           → Handler（出口：文件 / 控制台）
               → 闸② Handler 的 level
                   → Formatter（格式化）→ 落盘
```

| 角色 | 作用 | 本项目对应 |
|------|------|-----------|
| Logger | 代码里喊话的人 | `logging.getLogger("multi_agents.ecommerce")`（`runner.py:42` 模块级） |
| Handler | 出口，决定写到哪 | `logging.FileHandler(log_path)`（写文件，utf-8 支持中文） |
| Level | 门禁，多重要才放行 | `INFO`（`DEBUG < INFO < WARNING < ERROR < CRITICAL`） |
| Formatter | 每行长啥样 | `_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"` |

#### 关键坑：两道 level 闸都要开

一条 INFO 日志要**连过两道闸**才写出去：

- **闸① Logger 自己的 level**（Python 默认 `WARNING`！）
- **闸② Handler 的 level**（`_setup_run_log` 设了 `INFO`）

只开闸②、不开闸① → INFO 在闸①就被默认的 WARNING 拦掉 → **文件是空的**。所以 `_setup_run_log` 末尾主动把闸①也开到 INFO：

```python
if ecommerce_logger.level == logging.NOTSET or ecommerce_logger.level > logging.INFO:
    ecommerce_logger.setLevel(logging.INFO)   # 主动把闸①也开到 INFO
```

> 记忆：handler 的闸要开，logger 的闸也要开，**两道都开日志才通**。

#### 冒泡（propagate）：挂一个 handler 收全链路

Logger 按名字点分成树（`root → multi_agents → multi_agents.ecommerce → ...agents.review_insight`）。子 logger 喊的日志会**自动冒泡给父 logger 的所有 handler**。所以只在父 logger `multi_agents.ecommerce` 挂一个 FileHandler，子模块（各 agent / graph）的日志就全收进同一个文件——不用每个模块各配一遍。

#### 三步生命周期（每次研究一轮）

| 阶段 | 函数 | 干什么 |
|------|------|--------|
| 挂 | `_setup_run_log` | 建 FileHandler（指向本次 `<时间戳>_<关键词>.log`）+ 开两道闸 + 挂到 logger；返回 `(handler, log_path)` |
| 跑 | graph 全程 | 靠冒泡，graph / 各 agent / LLM 的日志自动落进本次文件 |
| 摘 | `_teardown_run_log` | `removeHandler`（不再写）+ `flush`（刷盘不丢）+ `close`（关句柄防泄漏） |

`_teardown_run_log` 在 `run_ecommerce_research` 里调 **2 次**：策略校验失败抛错前一次、跑 graph 的 `finally` 一次（不管成败都摘）。返回的 `handler` 仅供结束时摘掉（资源），`log_path` 用于日志末尾提示路径 + 塞进 `output_paths["log"]` 返回给前端（数据）。

#### 为什么每次研究都要「新挂新摘」

`FileHandler` 创建时就绑定**一个具体文件**，而每次研究的 `log_path` 都不同（时间戳保证唯一）。如果挂上不摘：

- logger 上**越积越多 handler**（每次研究一个）；
- 第 N 次研究喊一条日志，会**同时写进所有还挂着的旧文件** → 日志串了；
- 每个 handler 占一个文件句柄 → **泄漏**。

所以「新挂（指向本次文件）→ 用 → 摘」是必须的循环。`run_ecommerce_research` 用 `try/finally` 保证不管成功失败都摘 handler。

#### root logger 与兜底（lastResort）

- `logging.getLogger()`（空参）才是 root（树根），`getLogger("multi_agents.ecommerce")` 是它的后代；`getLogger("同名")` 是全局单例，同名永远返回同一对象（所以 `runner.py:42` 的模块级 `logger` 和 `_setup_run_log` 内的 `ecommerce_logger` 是同一个，前者用来喊话、后者用来挂 handler）。
- 啥都没配时，`WARNING+` 日志会被系统兜底 handler（lastResort）打到 stderr——这就是「没配过却看到控制台有日志」的原因。
- 本项目主动在 `multi_agents.ecommerce` 挂 FileHandler + 开 INFO 闸，把 INFO+ 落进按次文件。

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
  "overall_score": 6.92,
  "confidence": 0.88,          # 研究节点平均置信度(排除质检)
  "evidence_count": 18,        # 三方证据总数
  "fallback_count": 0,         # 非 success 的 agent 数
  "duration_ms": 56943,
  "recommendation": "...",
  "scored_by": "llm",
  "quality_passed": true,
  "review_source": "web_fallback",  # apify | web_fallback（评论来自哪）
  "review_count": 13,          # 抓到的评论数
  "failure_count": 0,          # governance: 执行失败次数
  "retry_count": 0,            # governance: 累计重试次数
  "policy_block_count": 0,     # governance: 策略拦截次数
  "llm_call_count": 1,         # governance: LLM 调用次数
  "search_call_count": 12,     # governance: 检索调用次数
  "estimated_cost_usd": 0.0    # governance: 累计估算成本
}
```
供 runner 写 `evaluation.json`、demo 导出、评估对比页统一消费。

---

## 11.5 运行时治理层（Runtime Governance）

> 治理层「包」在 Agent 图的外围，而非塞进某个 Agent 内部。四个职责模块协同：

| 模块 | 职责 | 落点 |
|------|------|------|
| `PolicyGuard` | 执行前校验请求（query / depth / market / platforms）、Agent 级工具权限、不安全 URL 过滤（file / loopback / 私网）、密钥脱敏 | `runtime/policy_guard.py`，runner 入口 + source_normalizer |
| `BudgetManager` | 执行中按 LLM / search / external_api 配额计费，超额自动降级（如 LLM 预算耗尽 → 规则评分） | `runtime/budget_manager.py`，scoring / search / scraper |
| `ExecutionGuard` | 包裹高风险调用，提供 timeout / retry / fallback，记录每次重试与降级事件 | `runtime/execution_guard.py` |
| Telemetry | `record_event` / `summarize_governance` 把上述事件合并进 `state["governance"]` → audit_log → evaluation_summary | `runtime/telemetry.py` |

**关键设计**：`graph._fresh_child` 让并发子状态**共享**主状态的 `governance` dict 引用（trend / competitor / review 的结果字段仍各自独立），因此 review 分支在子状态里记录的降级事件能无损回流到主状态，最终进入 `evaluation.json` 与评估对比页（重试 / 策略拦截 / LLM·Search 调用等列）。

**生产接入点**：

- `run_ecommerce_graph()` 用 `ExecutionGuard` 包裹 trend / competitor / review 三个并发研究节点；单个节点异常会记录 governance failure，并转成 partial 子状态继续合并，避免整条工作流直接中断。
- `make_budgeted_search_fn()` 在 Trend / Competitor / Review 三个 Agent 各自的 search 调用前执行工具权限检查与 search 预算检查；超预算会记录 budget degradation 并返回空结果。
- `ApifyReviewScraper` 在 Amazon product search / review fetch 两类 `requests.post` 前检查 `external_api` 预算；预算耗尽时不会发出外部 API 请求，而是返回空结果交给 ReviewInsightAgent 降级 Tavily。
- `ExecutionGuard` 写入 governance error event 前会通过 `PolicyGuard.redact_secrets()` 对 `TOKEN=...` / `api_key=...` / `password=...` 等错误消息做脱敏。

预算阈值可通过环境变量 `ECOMMERCE_MAX_LLM_CALLS` / `ECOMMERCE_MAX_SEARCH_CALLS` / `ECOMMERCE_MAX_EXTERNAL_API_CALLS` / `ECOMMERCE_MAX_ESTIMATED_COST_USD` 覆盖（见 `config.get_budget_config()`）。

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

---

## 17. 端到端 SOP 与数据流全程示例（portable blender）

> 本章把 7 个节点逐个讲透（读什么 / 做什么 / 写什么 / 记什么审计），再用 `query="portable blender", market="US", depth="standard"` 跑一遍，**展示每一步 state 里数据怎么变化**。是 §6（速览）和 §7（Agent 详解）的「带数据的完整版」。

### 17.0 数据流总览

```
START → planner → ┬─ trend     ─┐
                  ├─ competitor ├→ scoring → writer → quality → END
                  └─ review     ─┘
                  (fork 并发)     (join barrier)
```

| 节点 | 读 | 写（产出字段） | audit agent 名 | 同步/异步 |
|------|----|----|------|------|
| **planner** | query/market/depth | `research_plan` | ProductResearchPlannerAgent | 同步 |
| **trend** | `research_plan.trend_queries` | `trend_result` | TrendResearchAgent | 异步·并发 |
| **competitor** | `research_plan.competitor_queries` | `competitor_result` | CompetitorAnalysisAgent | 异步·并发 |
| **review** | `research_plan.review_queries` + governance | `review_result` | ReviewInsightAgent | 异步·并发 |
| **scoring** | trend/competitor/review_result | `opportunity_score` | OpportunityScoringAgent | 异步 |
| **writer** | opportunity_score + 三方 result | `final_report` | EcommerceReportWriterAgent | 同步 |
| **quality** | final_report + 三方 evidence | `quality_check` | QualityReviewerAgent | 同步 |

> 每个节点结束都往 `audit_log` 追加一条（`finalize_audit`），`governance` 走闭包共享原地改（不在 return 里）。

---

### 17.1 planner — 分工派活（同步，`agents/planner.py`）

| | 内容 |
|---|---|
| 📖 读 | `query` / `target_market` / `depth` |
| ⚙️ 做 | 按 depth 取 `max_queries`（fast=2/standard=4/deep=6），用 `_QUERY_TEMPLATES` 模板填充生成三类查询；**不触网、不调 LLM** |
| ✏️ 写 | `research_plan = {trend_queries, competitor_queries, review_queries, risk_focus, scoring_dimensions}` |
| 📋 audit | `{agent: ProductResearchPlannerAgent, status:success, source_count:0, confidence:1.0}`（没检索没花钱，确定性 100%） |

`risk_focus`（固定 4 项，给 quality 用）+ `scoring_dimensions`（固定 6 项，给 scoring 用）**不拿去检索**，只是契约清单。

---

### 17.2 trend — 趋势研究（异步并发，`agents/trend_researcher.py`）

| | 内容 |
|---|---|
| 📖 读 | `research_plan.trend_queries`（逐条检索，每条取 3 条结果）、query/market |
| ⚙️ 做 | `search_sources` 检索→标准化→url 去重→截断到 `max_sources_per_agent`；把 snippet/content 拼给 LLM 写中文趋势 summary，LLM 不可用回退模板 |
| ✏️ 写 | `trend_result = {summary, summary_source, trend_score, key_findings, evidence, confidence, scored_by?, negative_signals?, scoring_rationale?}` |
| 📋 audit | `{TrendResearchAgent, status, source_count, confidence, warning}` |

**评分逻辑**：`trend_score = 7.0 if source_count>=3 else 5.5`；`confidence = min(0.9, 0.35 + source_count*0.1)`；`source_count<2` → status=partial。失败兜底：trend_score=4.0, confidence=0.2。

**内容感知评分**：LLM 可用且返回 JSON 合法时，`trend_score` 来自 source content 的趋势强度、需求变化和负面信号分析，并返回 `scored_by="llm"`、`negative_signals`、`scoring_rationale`；LLM 不可用或 JSON 无效时，沿用 source-count 规则兜底，并标记 `scored_by="rule"`。

---

### 17.3 competitor — 竞品分析（异步并发，`agents/competitor_analyzer.py`）

| | 内容 |
|---|---|
| 📖 读 | `research_plan.competitor_queries`、query/market |
| ⚙️ 做 | 检索同 trend；正则 `\$(\d+)` 抽价格区间；LLM 写中文竞品 summary（回退模板）；从 source title 抽真实竞品名（去重，最多 3 个） |
| ✏️ 写 | `competitor_result = {summary, summary_source, competitors, price_range, competition_score, differentiation_opportunities, evidence, confidence, scored_by?, entry_barriers?, scoring_rationale?}` |
| 📋 audit | `{CompetitorAnalysisAgent, ...}` |

**评分逻辑**：`competition_score = 6.0 if source_count>=3 else 5.0`；`price_range` 默认 `$20-$60`（抽不到时）；`confidence = min(0.9, 0.35 + source_count*0.1)`。

**内容感知评分**：`competition_score` 表示竞争切入容易度。LLM 可用且返回 JSON 合法时，分数来自竞品强度、价格拥挤度、进入壁垒和差异化空间，并返回 `scored_by="llm"`、`entry_barriers`、`scoring_rationale`；LLM 不可用或 JSON 无效时，沿用 source-count 规则兜底，并标记 `scored_by="rule"`。

---

### 17.4 review — 评论洞察（异步并发，`agents/review_insight.py`）

| | 内容 |
|---|---|
| 📖 读 | `research_plan.review_queries`、query/market、governance（计外部 API） |
| ⚙️ 做 | 双数据源：有 Apify token → 抓 Amazon/Reddit 真实评论；失败/空/不相关 → 降级 Tavily fallback；LLM 把评论归纳中文痛点（回退原文） |
| ✏️ 写 | `review_result = {summary, pain_points, review_source, search_keyword, review_count, platforms, fallback_reason, pain_point_score, evidence, confidence, pain_points_language, scored_by?, structural_risks?, scoring_rationale?, ...}` |
| 📋 audit | `{ReviewInsightAgent, ..., review_source, search_keyword, review_count, platforms, fallback_reason}`（多 5 个扩展字段） |

**评分逻辑**：`pain_point_score = 8.0 if len(pain_points)>=3 else 5.5`；`confidence = min(0.9, 0.3 + len(pain_points)*0.08)`。

**内容感知评分**：`pain_point_score` 表示可行动的未满足需求机会。LLM 可用且返回 JSON 合法时，分数来自痛点频次、具体度、可解决性和结构性风险，并返回 `scored_by="llm"`、`structural_risks`、`scoring_rationale`；LLM 不可用或 JSON 无效时，沿用 pain-point-count 规则兜底，并标记 `scored_by="rule"`。

---

### 17.5 scoring — 机会评分（异步，`agents/opportunity_scorer.py`）

| | 内容 |
|---|---|
| 📖 读 | `trend_result` / `competitor_result` / `review_result`（取各 `*_score`） |
| ⚙️ 做 | 先取规则基线分；预算够则 LLM 打五维分（覆盖基线）+ 给理由，LLM 不可用/解析失败→保留规则；`evidence_score` 永远规则算；`overall_score` 按固定加权公式重算 |
| ✏️ 写 | `opportunity_score = {trend/competition/pain_point/margin/risk/evidence_score, overall_score, recommendation, reasons, scored_by}` |
| 📋 audit | `{OpportunityScoringAgent, status:success, source_count:evidence_count, confidence, warning}` |

**关键公式**：
- 规则基线：`trend=trend_result.trend_score`、`competition=competitor_result.competition_score`、`pain_point=review_result.pain_point_score`、`margin=6.0`、`risk=5.0`
- `evidence_score = min(10, 3 + evidence_count)`（evidence_count = 三方 evidence 数之和）
- **加权**（`schemas/scoring.py`）：trend×0.22 + competition×0.18 + pain_point×0.22 + margin×0.14 + risk×0.10 + evidence×0.14
- `recommendation`：≥7.5「建议进入但需小规模测试」/ ≥6.0「建议谨慎测试进入」/ <6.0「暂不建议」
- `confidence`：LLM 用了 = `min(0.9, 0.3+evidence*0.08)`；降级到规则 = 再 ×0.8（让评估页看出降级）
- 预算耗尽 → 强制 `llm_fn=None`（降级），记 governance 降级事件

---

### 17.6 writer — 报告生成（同步，`agents/report_writer.py`）

| | 内容 |
|---|---|
| 📖 读 | `opportunity_score` / `review_result` / `competitor_result` / `trend_result` / query / market |
| ⚙️ 做 | 按 `REPORT_SECTIONS` 固定 10 节顺序拼 Markdown；引用来自三方 evidence 的 url，去重后编号列出；第 7 节固定列通用方法论风险 |
| ✏️ 写 | `final_report`（Markdown 字符串） |
| 📋 audit | `{EcommerceReportWriterAgent, status:success, source_count:len(citations), confidence:0.8}` |

---

### 17.7 quality — 质量检查（同步，`agents/quality_reviewer.py`）

| | 内容 |
|---|---|
| 📖 读 | `final_report` + 三方 `evidence` + `review_result.pain_points` |
| ⚙️ 做 | 数报告里的 `http(s)://` 引用数；数三方 evidence 总数；基于真实痛点判 `risk_disclosure`；扫「稳赚/必爆/没有风险」等过度自信词 |
| ✏️ 写 | `quality_check = {passed, citation_coverage, evidence_sufficiency, logic_consistency, risk_disclosure, issues}` |
| 📋 audit | `{QualityReviewerAgent, status:success/partial, source_count:evidence_count, confidence:0.8, warning}` |

**基准**：`citation_coverage = min(1, 引用数/3)`；`evidence_sufficiency = min(1, evidence总数/6)`；`risk_disclosure = len(pain_points)>0`；任一不达标或有过自信词 → `issues` 非空 → `passed=False`。

---

### 17.8 贯穿示例：`portable blender / US / standard` 全程 state 变化

> 假设检索正常（trend/competitor 各搜到 4 条 source、review 得到 3 条痛点、价格抽到 $25-$45、最终引用 5 条）。下面每步只列**该步变化的字段**。

#### ▸ 初始 state（`create_initial_state`）
```python
{
  "query": "portable blender", "target_market": "US", "depth": "standard",
  "research_plan": {}, "trend_result": {}, "competitor_result": {}, "review_result": {},
  "opportunity_score": {}, "final_report": "", "quality_check": {},
  "audit_log": [], "errors": [],
  "governance": {"events": [], "usage": {"llm_call_count":0,"search_call_count":0,
                  "external_api_call_count":0,"estimated_cost_usd":0.0},
                 "budget_exceeded": False, "degraded_by_budget": False},
}
```

#### ▸ Step 1 planner（max_queries=4）
```python
"research_plan": {
  "trend_queries":      ["portable blender market trend US", "portable blender demand seasonality US",
                         "portable blender google trends US", "portable blender consumer trend report"],
  "competitor_queries": ["portable blender amazon best sellers", "portable blender top products amazon",
                         "best portable blender reviews", "portable blender price comparison"],
  "review_queries":     ["portable blender customer complaints US", "portable blender amazon reviews US",
                         "portable blender negative reviews US", "portable blender reddit review US"],
  "risk_focus":         ["platform policy risk","shipping and after-sales risk",
                         "product quality complaints","data source limitation"],
  "scoring_dimensions": ["trend_score","competition_score","pain_point_score",
                         "margin_score","risk_score","evidence_score"],
}
"audit_log": [+1]  # ProductResearchPlannerAgent, source_count=0, confidence=1.0
```

#### ▸ Step 2~4 三路并发（trend / competitor / review）
```python
"trend_result": {            # 搜到 4 source
  "summary": "<LLM 中文趋势总结>", "summary_source": "llm",
  "trend_score": 7.0,        # 4>=3 → 7.0
  "evidence": [<4 条>], "confidence": 0.75,   # min(0.9, 0.35+4*0.1)
}
"competitor_result": {       # 搜到 4 source
  "summary": "<LLM 中文竞品总结>", "summary_source": "llm",
  "competitors": [{name:"...",positioning:"..."}, ...3 个],
  "price_range": "$25-$45",  # 正则抽出
  "competition_score": 6.0,  # 4>=3 → 6.0
  "evidence": [<4 条>], "confidence": 0.75,
}
"review_result": {           # 抓到 3 条痛点（Apify 降级 Tavily）
  "pain_points": ["电池续航差","清洗麻烦","漏水"],
  "review_source": "web_fallback", "fallback_reason": "apify returned 0 reviews",
  "pain_point_score": 8.0,   # 3>=3 → 8.0
  "evidence": [<3 条>], "confidence": 0.54,   # min(0.9, 0.3+3*0.08)
}
"audit_log": [+3]            # Trend / Competitor / Review 三条
"governance.usage": {search:12, external_api:1, llm:2}  # 三路检索+评论+summary
```

#### ▸ Step 5 scoring（假设 LLM 不可用 → 规则评分，scored_by=rule）
```python
# 基线：trend=7.0, competition=6.0, pain_point=8.0, margin=6.0, risk=5.0
# evidence_count = 4+4+3 = 11 → evidence_score = min(10, 3+11) = 10.0
# overall = 7.0×0.22 + 6.0×0.18 + 8.0×0.22 + 6.0×0.14 + 5.0×0.10 + 10.0×0.14
#         = 1.54 + 1.08 + 1.76 + 0.84 + 0.50 + 1.40 = 7.12
"opportunity_score": {
  "trend_score":7.0, "competition_score":6.0, "pain_point_score":8.0,
  "margin_score":6.0, "risk_score":5.0, "evidence_score":10.0,
  "overall_score": 7.12,
  "recommendation": "建议谨慎测试进入",   # 7.12 ∈ [6.0, 7.5)
  "reasons": [<规则 3 条理由>], "scored_by": "rule",
}
"audit_log": [+1]  # OpportunityScoringAgent, source_count=11, confidence=0.72 (0.9×0.8 降级打折)
#                 warning="llm scoring unavailable, fallback to rule"
```

#### ▸ Step 6 writer（拼 10 节 Markdown）
```python
"final_report": "# 跨境电商选品调研报告\n## 1. 选品结论\n建议谨慎测试进入。...\n## 2. 市场趋势分析\n...
                 \n## 7. 风险因素\n...\n## 10. 数据来源与引用\n1. [...]...\n2. [...]..."  # 含 5 条引用
"audit_log": [+1]  # EcommerceReportWriterAgent, source_count=5 (citations), confidence=0.8
```

#### ▸ Step 7 quality
```python
# citation_count=5 → citation_coverage = min(1, 5/3) = 1.0
# evidence 总数 11 → evidence_sufficiency = min(1, 11/6) = 1.0
# pain_points=3 → risk_disclosure = True
# 无过度自信词 → overconfident=[]
"quality_check": {
  "passed": True, "citation_coverage":1.0, "evidence_sufficiency":1.0,
  "logic_consistency":0.8, "risk_disclosure":True, "issues":[],
}
"audit_log": [+1]  # QualityReviewerAgent, status=success, source_count=11, confidence=0.8
# audit_log 现共 7 条（7 个 agent 各一）
```

---

### 17.9 最终产物（runner 落盘）

graph 跑完，`run_ecommerce_graph` 把闭包改过的 governance 赋回 `final["governance"]`，然后 runner 写 4 个文件 + 回填路径：

| 文件 | 内容 | 来源字段 |
|------|------|---------|
| `portable-blender-report.md` | 选品报告（Markdown） | `final_report` |
| `portable-blender-audit.json` | 7 条审计记录 | `audit_log` |
| `portable-blender-quality.json` | 质检结果 | `quality_check` |
| `portable-blender-evaluation.json` | 评估汇总（总分/置信度/证据数/降级数/耗时/评分方式/质检） | `build_evaluation_summary(final_state)` |

```python
final_state["output_paths"] = {
  "report":"outputs/ecommerce/portable-blender-report.md",
  "audit":"...portable-blender-audit.json",
  "quality":"...portable-blender-quality.json",
  "evaluation":"...portable-blender-evaluation.json",
  "log":"logs/ecommerce/<时间戳>_portable-blender.log",
}
final_state["evaluation_summary"] = {  # evaluation.json 的内容
  "overall_score":7.12, "scored_by":"rule", "passed":True,
  "avg_confidence": <7 条 audit confidence 的均值>, "evidence_count":11,
  "degradation_count": <governance 里 fallback/retry 事件数>, "total_duration_ms": <7 条 duration 之和>,
  ...governance 汇总字段,
}
```

### 17.10 全程数据变化一图流（portable blender）

```
state 字段         planner   trend/comp/review(并发)   scoring    writer    quality   落盘
─────────────────  ────────  ──────────────────────    ────────   ────────  ────────  ────
research_plan      ✅写入
trend_result                  ✅写入
competitor_result             ✅写入
review_result                 ✅写入
opportunity_score                                       ✅写入
final_report                                                      ✅写入
quality_check                                                               ✅写入
audit_log          +1         +3                        +1         +1        +1        → audit.json(7条)
governance         (闭包改)   (闭包改:usage+events)     (闭包改)                                  → 喂 evaluation
                                                                     ─────────────────────────
                                                       4 个文件 ← report/audit/quality/evaluation
```

> 核心记忆：**每个节点只写自己负责的字段**（planner→plan、trend→trend_result…），`audit_log` 靠 `operator.add` reducer 自动累加成 7 条，`governance` 全程闭包原地改（不进 return），最后 runner 把所有结果落盘 + 聚合成 evaluation。
