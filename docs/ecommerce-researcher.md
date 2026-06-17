# EcomResearcher：跨境电商 AI 选品与市场调研助手

EcomResearcher 是基于 GPT Researcher / LangGraph 二次开发的**跨境电商垂直领域多 Agent 工作流**。
输入一个品类关键词，自动完成市场趋势、竞品格局、用户评论痛点的研究，
生成机会评分、结构化选品报告、质量检查结果与执行审计日志。

> 这是一个面向 LLM 应用岗的简历项目改造：在成熟开源研究系统上做垂直场景落地，
> 而不是从零造轮子。

## 快速开始

```bash
# 1. 安装依赖（项目根目录）
pip install -r requirements.txt

# 2. 配置 .env（至少需要检索器 key，默认用 Tavily）
#    TAVILY_API_KEY=...

# 3. 运行（独立入口，不改动原 cli.py）
python -m multi_agents.ecommerce \
  --query "portable blender" \
  --market "US" \
  --platforms amazon,google \
  --depth standard
```

输出文件（默认写到 `outputs/ecommerce/`）：

```text
outputs/ecommerce/portable-blender-report.md     # 选品调研报告（Markdown）
outputs/ecommerce/portable-blender-audit.json    # 各 Agent 执行审计日志
outputs/ecommerce/portable-blender-quality.json  # 报告质量检查结果
```

## 工作流

```text
用户输入（品类 / 市场 / 平台 / 深度）
  │
  ▼
ProductResearchPlannerAgent          # 拆解为趋势/竞品/评论/风险查询
  │
  ▼  并发执行（asyncio.gather）
  ├─ TrendResearchAgent              # 市场趋势 + 趋势分
  ├─ CompetitorAnalysisAgent         # 竞品 + 价格区间 + 竞争分
  └─ ReviewInsightAgent              # 评论痛点 + 痛点分
  │
  ▼
OpportunityScoringAgent              # 6 维加权 → overall_score + 是否建议进入
  │
  ▼
EcommerceReportWriterAgent           # 固定 10 节 Markdown 报告 + 引用
  │
  ▼
QualityReviewerAgent                 # 引用覆盖率 / 证据充分度 / 风险披露 / 过度确定性
```

## 核心设计

| 模块 | 职责 |
|------|------|
| `state.py` | 统一共享状态 `EcommerceResearchState`，节点只读写各自字段 |
| `config.py` | fast / standard / deep 三档深度参数 |
| `tools/` | 数据源标准化、查询构造、评论痛点抽取；`search_fn` 可注入 |
| `agents/` | 7 个业务 Agent，失败统一降级、不中断主流程 |
| `graph.py` | LangGraph 风格编排，三个研究节点并发 |
| `runner.py` | 端到端入口 + 文件输出 + 默认检索器适配 |
| `schemas/` | 评分加权、报告章节结构 |

### 可观测性与可靠性

- **审计日志**：每个 Agent 记录 `status / duration_ms / source_count / confidence / warning`。
- **失败降级**：检索失败、JSON 异常、数据不足都走 fallback，保证端到端不崩。
- **质量评估**：检查引用覆盖率、证据充分度、风险披露，并拦截"稳赚/必爆"等过度确定性表述。

## 调研深度

| depth | max_queries | max_sources | 适用 |
|-------|-------------|-------------|------|
| fast | 2 | 3 | 快速预览 |
| standard | 4 | 6 | 默认 |
| deep | 6 | 10 | 更完整 |

## 测试

```bash
python -m pytest tests/test_ecommerce_state.py tests/test_ecommerce_tools.py \
                 tests/test_ecommerce_agents.py tests/test_ecommerce_runner.py -v
```

共 28 个单测，覆盖状态、工具、7 个 Agent、端到端 runner、失败降级、零数据源场景。
所有网络检索通过注入 `fake_search` 解耦，测试不触网。

## MVP 边界（明确不做）

- 不做完整 Amazon / TikTok Shop 爬虫
- 不做数据库持久化、用户系统
- 不做真实销量预测、供应链成本建模、Listing 自动生成

这些作为后续扩展方向。第一版以公开搜索结果与评论片段为主要数据源，
评分是**选品辅助决策**，不代表销量预测。

## 程序化调用

```python
import asyncio
from multi_agents.ecommerce import run_ecommerce_research

result = asyncio.run(run_ecommerce_research(
    query="portable blender",
    target_market="US",
    platforms=["amazon", "google"],
    depth="standard",
))

print(result["final_report"])
print(result["opportunity_score"]["overall_score"])
print(result["quality_check"])
```

## API 与前端（可选）

### FastAPI 端点
启动后端：`python -m uvicorn main:app --port 8000`

- `POST /api/ecommerce/research`：请求体 `{query, target_market, platforms, depth, use_llm}`，同步返回 `report / opportunity_score / quality_check / audit_log`。
- `WS /ws/ecommerce`：发 `{query,...}` 后，逐阶段推送 `start → planner_done → research_running → research_done → scoring_done → report_done → quality_done`，最后 `done` 事件回传完整结果。

路由以独立 `APIRouter` 注册（`backend/server/ecommerce_api.py`），不侵入主路由。

### 前端页面
启动后端后访问：`http://localhost:8000/site/ecommerce.html`

- 输入品类关键词、目标市场、深度，勾选「启用 LLM 打分」
- 实时显示 8 段执行进度时间线（WebSocket 推送）
- 机会评分（6 维雷达图）+ 质量检查 + Agent 执行链路表 + Markdown 报告渲染

## 简历表达

> 基于 GPT Researcher 和 LangGraph 二次开发跨境电商垂直领域多 Agent 工作流，
> 构建趋势研究、竞品分析、评论洞察、机会评分、报告生成和质量审查等 Agent，
> 实现从品类输入到结构化选品报告输出的自动化闭环。
> 引入 Agent 执行审计日志与质量评估机制（引用覆盖率、证据充分度、逻辑一致性、风险披露），
> 并通过 query 扩展、失败降级提升长链路多 Agent 任务的稳定性。

## 相关文档

- 设计文档：`docs/superpowers/specs/2026-06-18-ecommerce-research-agent-design.md`
- 实现计划：`docs/superpowers/plans/2026-06-18-ecommerce-research-agent.md`
