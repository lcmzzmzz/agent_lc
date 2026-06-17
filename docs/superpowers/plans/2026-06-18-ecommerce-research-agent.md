# EcomResearcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-border ecommerce product research workflow on top of GPT Researcher’s multi-agent module.

**Architecture:** Add a self-contained `multi_agents/ecommerce/` workflow with typed state, schemas, lightweight search tools, business-specific agents, graph orchestration, an independent CLI entrypoint, audit logs, quality checks, and markdown/json outputs. Keep the first version minimally invasive and avoid platform-specific scraping.

**Tech Stack:** Python, pytest (asyncio_mode=strict), LangGraph, GPT Researcher retriever utilities, asyncio, TypedDict.

---

## 现有代码接入点（已确认）

- 检索器工厂：`gpt_researcher/actions/retriever.py`
  - `get_retriever(name: str)`：按名称返回检索器**类**（不是按 query）。
  - `get_default_retriever()`：返回 `TavilySearch` 类。
- 检索器用法（参考 `Duckduckgo`）：`Duckduckgo(query, query_domains).search(max_results=5)`，返回 `[{"title","href","body"}, ...]`。
- 原有 `cli.py` 的 `query` 是位置参数、`--report_type` 必填，**不改它**；新增独立入口 `python -m multi_agents.ecommerce`。
- pytest 配置：`asyncio_mode = "strict"`，异步测试需要 `@pytest.mark.asyncio`。

---

## File Structure

### Create

- `multi_agents/ecommerce/__init__.py`
- `multi_agents/ecommerce/state.py`
- `multi_agents/ecommerce/config.py`
- `multi_agents/ecommerce/prompts.py`
- `multi_agents/ecommerce/schemas/__init__.py`
- `multi_agents/ecommerce/schemas/scoring.py`
- `multi_agents/ecommerce/schemas/report.py`
- `multi_agents/ecommerce/tools/__init__.py`
- `multi_agents/ecommerce/tools/source_normalizer.py`
- `multi_agents/ecommerce/tools/product_search.py`
- `multi_agents/ecommerce/tools/review_extractor.py`
- `multi_agents/ecommerce/agents/__init__.py`
- `multi_agents/ecommerce/agents/planner.py`
- `multi_agents/ecommerce/agents/trend_researcher.py`
- `multi_agents/ecommerce/agents/competitor_analyzer.py`
- `multi_agents/ecommerce/agents/review_insight.py`
- `multi_agents/ecommerce/agents/opportunity_scorer.py`
- `multi_agents/ecommerce/agents/report_writer.py`
- `multi_agents/ecommerce/agents/quality_reviewer.py`
- `multi_agents/ecommerce/graph.py`
- `multi_agents/ecommerce/runner.py`
- `multi_agents/ecommerce/__main__.py`
- `tests/test_ecommerce_state.py`
- `tests/test_ecommerce_tools.py`
- `tests/test_ecommerce_agents.py`
- `tests/test_ecommerce_runner.py`

### Modify

- 不修改原 `cli.py`（用独立入口）。

---

## Task 1: State, Config, and Schemas

**Files:**
- Create: `multi_agents/ecommerce/__init__.py`
- Create: `multi_agents/ecommerce/state.py`
- Create: `multi_agents/ecommerce/config.py`
- Create: `multi_agents/ecommerce/prompts.py`
- Create: `multi_agents/ecommerce/schemas/__init__.py`
- Create: `multi_agents/ecommerce/schemas/scoring.py`
- Create: `multi_agents/ecommerce/schemas/report.py`
- Test: `tests/test_ecommerce_state.py`

- [ ] **Step 1: Write failing state tests** — `tests/test_ecommerce_state.py`
- [ ] **Step 2: Run test to verify it fails** — `pytest tests/test_ecommerce_state.py -v`
- [ ] **Step 3: Create package exports** — `__init__.py`, `schemas/__init__.py`
- [ ] **Step 4: Implement config** — `config.py`（fast/standard/deep 三档）
- [ ] **Step 5: Implement state** — `state.py`（`EcommerceResearchState` + `create_initial_state`）
- [ ] **Step 6: Implement scoring schema** — `schemas/scoring.py`（`clamp_score` + `calculate_overall_score`）
- [ ] **Step 7: Implement report schema** — `schemas/report.py`（`REPORT_SECTIONS` + `build_report_title`）
- [ ] **Step 8: Implement prompts** — `prompts.py`（集中放各 Agent 的系统提示，预留）
- [ ] **Step 9: Run tests** — PASS
- [ ] **Step 10: Commit**

验收：`create_initial_state` 默认值正确；`get_depth_config` 返回 standard 限制并在未知 depth 时回退；`clamp_score` 限定 0–10；`calculate_overall_score` 加权平均落在合理区间。

---

## Task 2: Tools for Sources, Queries, and Review Extraction

**Files:**
- Create: `multi_agents/ecommerce/tools/__init__.py`
- Create: `multi_agents/ecommerce/tools/source_normalizer.py`
- Create: `multi_agents/ecommerce/tools/product_search.py`
- Create: `multi_agents/ecommerce/tools/review_extractor.py`
- Test: `tests/test_ecommerce_tools.py`

- [ ] **Step 1: Write failing tool tests** — `tests/test_ecommerce_tools.py`
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement tool exports** — `tools/__init__.py`
- [ ] **Step 4: Implement source normalizer** — 兼容 `href/body` 等字段，推断 `source_type`
- [ ] **Step 5: Implement product search helpers** — `build_ecommerce_queries`（trend/competitor/review/risk 四种意图）+ `search_sources`（注入 search_fn，去重）
- [ ] **Step 6: Implement review extractor** — `extract_review_insights`（按关键词句子抽取痛点）
- [ ] **Step 7: Run tests** — PASS
- [ ] **Step 8: Commit**

关键约束：
- `SearchFn = Callable[[str, int], Awaitable[list[dict]]]`，签名 `(query, max_results) -> list[dict]`。
- `search_sources` 接收注入的 `search_fn`，便于测试用 fake_search。

---

## Task 3: Planner, Research, and Insight Agents

**Files:**
- Create: `multi_agents/ecommerce/agents/__init__.py`
- Create: `multi_agents/ecommerce/agents/planner.py`
- Create: `multi_agents/ecommerce/agents/trend_researcher.py`
- Create: `multi_agents/ecommerce/agents/competitor_analyzer.py`
- Create: `multi_agents/ecommerce/agents/review_insight.py`
- Test: `tests/test_ecommerce_agents.py`

- [ ] **Step 1: Write failing agent tests**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement agent exports**
- [ ] **Step 4: Implement planner** — 同步，写 `research_plan` + audit log
- [ ] **Step 5: Implement trend researcher** — 异步，注入 search_fn，try/except 降级
- [ ] **Step 6: Implement competitor analyzer** — 异步，额外输出 `price_range`（正则提取 `$N`）
- [ ] **Step 7: Implement review insight** — 异步，调用 `extract_review_insights`
- [ ] **Step 8: Run tests** — PASS
- [ ] **Step 9: Commit**

关键约束：
- 每个节点只读写自己的字段，并向 `audit_log` 追加一条记录（含 `duration_ms`、`status`、`source_count`、`confidence`、`warning`）。
- 失败时返回 fallback 结构（低置信度），不 raise 中断。

---

## Task 4: Scoring, Report Writing, and Quality Review Agents

**Files:**
- Create: `multi_agents/ecommerce/agents/opportunity_scorer.py`
- Create: `multi_agents/ecommerce/agents/report_writer.py`
- Create: `multi_agents/ecommerce/agents/quality_reviewer.py`
- Modify: `tests/test_ecommerce_agents.py`

- [ ] **Step 1: Append failing tests** — scoring / writer / reviewer
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement opportunity scorer** — 汇总三维 + 证据数 → 6 维评分 + recommendation
- [ ] **Step 4: Implement report writer** — 固定 10 节 Markdown + 去重引用
- [ ] **Step 5: Implement quality reviewer** — citation_coverage / evidence_sufficiency / logic / risk_disclosure / 过度确定性
- [ ] **Step 6: Run tests** — PASS
- [ ] **Step 7: Commit**

关键约束：
- `recommendation` 阈值：>=7.5 建议进入；>=6.0 谨慎测试；否则暂不建议。
- 报告第 7 节必须包含“风险”与“销量预测”字样，确保 `risk_disclosure=True`。

---

## Task 5: Graph and Runner

**Files:**
- Create: `multi_agents/ecommerce/graph.py`
- Create: `multi_agents/ecommerce/runner.py`
- Test: `tests/test_ecommerce_runner.py`

- [ ] **Step 1: Write failing runner test** — 用 fake_search + tmp_path 校验三个输出文件
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement graph** — `run_planner` → `asyncio.gather(trend, competitor, review)` → scoring → writer → quality
- [ ] **Step 4: Implement runner** — `run_ecommerce_research()` + `slugify` + 写文件 + `default_search_fn`
- [ ] **Step 5: Run runner tests** — PASS
- [ ] **Step 6: Run all ecommerce tests** — PASS
- [ ] **Step 7: Commit**

`default_search_fn` 实现要点（修正原计划）：

```python
async def default_search_fn(query: str, max_results: int) -> list[dict]:
    from gpt_researcher.actions.retriever import get_default_retriever
    retriever_cls = get_default_retriever()       # 返回检索器类，如 TavilySearch
    retriever = retriever_cls(query=query)        # 实例化
    return retriever.search(max_results=max_results)
```

并发执行时注意：三个研究 Agent 各自 `state.copy()` 后跑，再合并结果和 audit log。

---

## Task 6: Independent CLI Entrypoint

**Files:**
- Create: `multi_agents/ecommerce/__main__.py`
- Test manually with configured retriever（fake_search 单测在 runner 已覆盖）。

- [ ] **Step 1: Implement argparse entrypoint** — `--query/--market/--platforms/--depth`
- [ ] **Step 2: Run help** — `python -m multi_agents.ecommerce --help`
- [ ] **Step 3: Run end-to-end** — `python -m multi_agents.ecommerce --query "portable blender" --depth fast`
- [ ] **Step 4: Verify output files** — `outputs/ecommerce/portable-blender-*.md|json`
- [ ] **Step 5: Commit**

入口逻辑：

```python
import argparse, asyncio
from multi_agents.ecommerce.runner import run_ecommerce_research

def main():
    parser = argparse.ArgumentParser(description="EcomResearcher ...")
    parser.add_argument("--query", required=True)
    parser.add_argument("--market", default="US")
    parser.add_argument("--platforms", default="amazon,google")
    parser.add_argument("--depth", default="standard", choices=["fast","standard","deep"])
    args = parser.parse_args()

    result = asyncio.run(run_ecommerce_research(
        query=args.query,
        target_market=args.market,
        platforms=[p.strip() for p in args.platforms.split(",") if p.strip()],
        depth=args.depth,
    ))
    print(f"Report:  {result['output_paths']['report']}")
    print(f"Audit:   {result['output_paths']['audit']}")
    print(f"Quality: {result['output_paths']['quality']}")

if __name__ == "__main__":
    main()
```

---

## Task 7: README and Demo Artifacts

**Files:**
- Create: `docs/ecommerce-researcher.md`
- Create: `outputs/ecommerce/demo-notes.md`（demo case 说明）

- [ ] **Step 1: Create documentation** — 用法 + 工作流图 + MVP 边界 + 简历描述
- [ ] **Step 2: Run demo cases** — portable blender / pet water fountain / standing desk
- [ ] **Step 3: Create demo notes**
- [ ] **Step 4: Commit**

---

## Self-Review

### Spec Coverage
- 垂直工作流：Tasks 1–7
- 状态 schema：Task 1
- 搜索/标准化：Task 2
- planner/trend/competitor/review：Task 3
- scoring/writer/quality：Task 4
- graph + runner：Task 5
- CLI 输出：Task 6
- demo/文档：Task 7
- 失败降级：Tasks 3–5（fallback + audit log）

### Placeholder Scan
无 TBD/TODO。

### Type Consistency
- state key：`trend_result / competitor_result / review_result / opportunity_score / final_report / quality_check / audit_log / errors`。
- search_fn 签名：`async (query: str, max_results: int) -> list[dict]`。
- runner 签名：`run_ecommerce_research(query, target_market, platforms, depth, output_dir, search_fn)`。
