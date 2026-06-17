# EcomResearcher：跨境电商 AI 选品与市场调研助手设计文档

> 创建日期：2026-06-18
> 状态：已确认，进入实现阶段
> 分支：`gpt_branch`

## 1. 项目背景

GPT Researcher 是一个通用型 LLM Research Agent 项目，具备搜索、抓取、规划、写作和多 Agent 协作能力。现有 `multi_agents/` 模块更偏通用研究报告生成，缺少明确的垂直业务场景。

为了让项目更适合作为 LLM 应用岗简历项目，本设计选择将其二次开发为跨境电商垂直领域助手，聚焦“选品与市场调研”场景。

跨境卖家在选品阶段通常需要分析：

- 目标市场趋势
- 竞品商品与价格区间
- 用户评论和差评痛点
- 差异化机会
- 进入风险
- 是否值得小规模测试

这些任务天然适合拆解为多个 Agent 并发执行，再汇总成结构化报告。

## 2. 项目目标

项目名称：

> **EcomResearcher：跨境电商 AI 选品与市场调研助手**

一句话目标：

> 基于 GPT Researcher 和 LangGraph 二次开发跨境电商垂直领域多 Agent 工作流，实现从品类输入到市场趋势、竞品分析、评论洞察、机会评分和结构化选品报告输出的自动化闭环。

MVP 目标：

1. 用户输入品类关键词、目标市场和平台偏好。
2. 系统自动生成调研计划。
3. 趋势研究、竞品分析、评论洞察并发执行。
4. 系统生成机会评分。
5. 系统输出结构化 Markdown 选品报告。
6. 系统输出质量检查结果。
7. 系统输出 Agent 执行审计日志。

## 3. 非目标范围（MVP 不做）

- 不做完整 Amazon 爬虫。
- 不接 TikTok Shop 正式 API。
- 不做复杂前端 Dashboard。
- 不做数据库持久化。
- 不做用户登录和权限系统。
- 不做真实销量预测。
- 不做供应链成本建模。
- 不做广告投放优化。
- 不做 Listing 自动生成。

这些内容可作为后续扩展方向，但不进入第一版实现范围。

## 4. 核心用户流程

示例输入：

```bash
python -m multi_agents.ecommerce \
  --query "portable blender" \
  --market "US" \
  --platforms amazon,google \
  --depth standard
```

系统执行流程：

```text
用户输入
  ↓
ProductResearchPlannerAgent 生成调研计划
  ↓
并发执行：
  ├─ TrendResearchAgent
  ├─ CompetitorAnalysisAgent
  └─ ReviewInsightAgent
  ↓
OpportunityScoringAgent 汇总评分
  ↓
EcommerceReportWriterAgent 生成报告
  ↓
QualityReviewerAgent 做质量检查
  ↓
输出报告、质量检查结果、审计日志
```

输出文件：

```text
outputs/ecommerce/portable-blender-report.md
outputs/ecommerce/portable-blender-audit.json
outputs/ecommerce/portable-blender-quality.json
```

## 5. 推荐代码结构

新增独立垂直模块：

```text
multi_agents/ecommerce/
  __init__.py
  graph.py
  state.py
  config.py
  prompts.py
  runner.py
  __main__.py            # 独立 CLI 入口：python -m multi_agents.ecommerce

  agents/
    __init__.py
    planner.py
    trend_researcher.py
    competitor_analyzer.py
    review_insight.py
    opportunity_scorer.py
    report_writer.py
    quality_reviewer.py

  tools/
    __init__.py
    product_search.py
    review_extractor.py
    source_normalizer.py

  schemas/
    __init__.py
    report.py
    scoring.py
```

设计原则：

- 尽量不侵入原有 GPT Researcher 主流程，不改 `cli.py`。
- 将跨境电商逻辑集中在 `multi_agents/ecommerce/`。
- prompt、schema、tools、agents 分层管理。
- 保持后续扩展其他垂直领域的可能性。

## 6. 状态设计

核心状态对象：`EcommerceResearchState`

字段：

```python
{
    "query": "portable blender",
    "target_market": "US",
    "platforms": ["amazon", "google"],
    "depth": "standard",

    "research_plan": {},
    "trend_result": {},
    "competitor_result": {},
    "review_result": {},
    "opportunity_score": {},
    "final_report": "",

    "quality_check": {},
    "audit_log": [],
    "errors": []
}
```

约束：

- 每个 Agent 只读写自己负责的字段。
- Agent 之间不直接传递散乱自然语言。
- 所有节点通过统一 state 流转。
- 错误信息统一写入 `errors` 和 `audit_log`。

## 7. LangGraph 工作流设计

```text
START
  ↓
planner
  ↓
并发：
  ├─ trend_research
  ├─ competitor_analysis
  └─ review_insight
  ↓
opportunity_scoring
  ↓
report_writer
  ↓
quality_reviewer
  ↓
END
```

## 8. Agent 设计

### 8.1 ProductResearchPlannerAgent
将用户输入拆成趋势、竞品、评论 query，明确评分维度和风险关注点。

### 8.2 TrendResearchAgent
分析品类热度、季节性、搜索需求、行业趋势，输出 `summary / trend_score / key_findings / evidence / confidence`。

### 8.3 CompetitorAnalysisAgent
分析 Top 竞品、价格区间、卖点、竞争强度、差异化空间。

### 8.4 ReviewInsightAgent
提取高频差评、用户痛点、购买动机、可转化为卖点的机会。

### 8.5 OpportunityScoringAgent
汇总趋势、竞品、评论结果，生成 6 维评分 + overall_score + 是否建议进入。

评分维度：
- `trend_score`
- `competition_score`
- `pain_point_score`
- `margin_score`
- `risk_score`
- `evidence_score`
- `overall_score`

### 8.6 EcommerceReportWriterAgent
生成固定结构 Markdown 报告。

报告结构：
1. 选品结论
2. 市场趋势分析
3. 竞品格局分析
4. 用户痛点与差评洞察
5. 差异化机会
6. 价格区间与利润空间初步判断
7. 风险因素
8. 机会评分
9. 是否建议进入
10. 数据来源与引用

### 8.7 QualityReviewerAgent
检查引用、证据充分度、逻辑一致性、风险披露、过度确定性表达。

## 9. 工具层设计

### 9.1 product_search.py
基于现有 web retriever 封装商品、竞品、趋势、评论相关搜索，不写复杂平台爬虫。

### 9.2 review_extractor.py
从网页内容、搜索摘要、评测文章、论坛内容中提取评论相关信息。

### 9.3 source_normalizer.py
统一来源格式：

```json
{
  "title": "...",
  "url": "...",
  "source_type": "amazon | google | reddit | blog | review_site",
  "snippet": "...",
  "content": "..."
}
```

## 10. 审计日志设计

每个 Agent 执行结束后写入 `audit_log`：

```json
{
  "agent": "TrendResearchAgent",
  "status": "success | partial",
  "duration_ms": 18200,
  "source_count": 6,
  "confidence": 0.8,
  "warning": null
}
```

## 11. 失败降级设计

### 11.1 搜索结果不足
自动 query expansion，降低置信度，在报告中提示数据不足。

### 11.2 JSON 解析失败
尝试修复 → 重新请求 → 返回默认降级结构 → 写入 audit log。

### 11.3 单 Agent 失败
不中断工作流，返回 fallback 结构，降低相关评分和置信度。

## 12. 质量评估设计

`QualityReviewerAgent` 至少检查 5 个维度：

1. 引用覆盖率
2. 证据充分度
3. 逻辑一致性
4. 风险披露
5. 过度确定性（避免“必爆”“稳赚”等表述）

## 13. CLI 入口设计

新增独立 CLI 入口（不改原 `cli.py`）：

```bash
python -m multi_agents.ecommerce \
  --query "portable blender" \
  --market "US" \
  --platforms amazon,google \
  --depth standard
```

参数：
- `query`：品类关键词（必填）
- `market`：目标市场，默认 `US`
- `platforms`：平台偏好，默认 `amazon,google`
- `depth`：调研深度，支持 `fast`、`standard`、`deep`

## 14. 验收标准

### 14.1 功能验收
- 可以输入品类关键词。
- 可以生成完整选品报告。
- 报告包含趋势、竞品、评论痛点、机会评分、风险提示。
- 报告包含引用来源。
- 输出审计日志。
- 输出质量检查结果。

### 14.2 工程验收
- Agent 职责清晰。
- 使用统一 state 流转。
- prompt 集中管理。
- schema 集中管理。
- 单节点失败不会导致整体崩溃。
- 有基础 query expansion。
- 有 JSON 修复或降级机制。

### 14.3 展示验收
准备 3 个 demo case：

```text
portable blender
pet water fountain
standing desk
```

每个 case 应提前生成报告、审计日志和质量检查结果。

## 15. 简历表达

项目名称：

> **EcomResearcher：跨境电商 AI 选品与市场调研助手**

项目描述：

> 基于 GPT Researcher 和 LangGraph 二次开发跨境电商垂直领域多 Agent 工作流，构建趋势研究、竞品分析、评论洞察、机会评分、报告生成和质量审查等 Agent，实现从品类输入到结构化选品报告输出的自动化闭环。

技术亮点：

- 基于 LangGraph 设计多 Agent 状态机，将选品调研拆分为趋势研究、竞品分析、评论洞察、机会评分和报告生成等节点，并支持多研究节点并发执行。
- 设计跨境选品评分体系，从趋势热度、竞争强度、用户痛点、价格空间、风险因素和证据充分度等维度生成机会评分。
- 引入 Agent 执行审计日志，记录节点耗时、执行状态、数据源数量和异常信息，提升长链路 Agent 任务的可观测性。
- 构建质量评估模块，检查报告引用覆盖率、证据充分度、逻辑一致性和风险披露，降低 LLM 生成结论的不可控性。
- 通过 query expansion、JSON 修复、数据不足 fallback 和单节点失败降级机制，提高多 Agent 工作流稳定性。

## 16. 风险与边界

- 真实平台数据可能受限，MVP 先以公开搜索结果和评论片段为主。
- 评分是辅助决策评分，不等于真实销售预测。
- 需避免在报告中输出过度确定性结论。
