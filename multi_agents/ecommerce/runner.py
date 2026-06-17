"""
EcomResearcher 运行入口与文件输出。

【正经注释】
run_ecommerce_research 是对外统一入口：构造初始状态 → 跑完整 graph →
把报告 / 审计日志 / 质量检查分别写成 .md / .json 文件。
default_search_fn 复用 GPT Researcher 的默认检索器（如 Tavily），
任何检索异常都被吞成空结果，交给下游 Agent 走降级路径，保证端到端不崩。

【大白话注释】
这是"一键启动"按钮：输入品类，跑完整条流程，
最后把报告、日志、质检结果分别存成文件。
默认的搜索用的是项目自带的搜索引擎；就算没配 key 搜不到，
也只是少点引用，报告照样能出。
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from multi_agents.ecommerce.graph import ProgressFn, run_ecommerce_graph
from multi_agents.ecommerce.llm_helper import LlmFn
from multi_agents.ecommerce.state import EcommerceResearchState, create_initial_state
from multi_agents.ecommerce.tools.product_search import SearchFn

_SLUG_RE = re.compile(r"[^\w]+", flags=re.UNICODE)


def slugify(value: str) -> str:
    """把品类关键词转成安全的文件名片段（兼容中英文，无结果时回退）。"""
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "ecommerce-research"


async def default_search_fn(query: str, max_results: int) -> list[dict[str, Any]]:
    """复用 GPT Researcher 默认检索器；任何异常都降级为空结果。

    检索器是同步阻塞 IO，用 asyncio.to_thread 放到线程池，
    让三个研究 Agent 的多次检索能真正并发执行。
    """

    def _sync_search() -> list[dict[str, Any]]:
        try:
            from gpt_researcher.actions.retriever import get_default_retriever

            retriever_cls = get_default_retriever()  # 例如 TavilySearch 类
            retriever = retriever_cls(query=query)
            return retriever.search(max_results=max_results) or []
        except Exception as exc:  # 检索失败不应中断主流程
            print(f"[ecommerce] default search failed for '{query}': {exc}")
            return []

    return await asyncio.to_thread(_sync_search)


async def run_ecommerce_research(
    *,
    query: str,
    target_market: str = "US",
    platforms: list[str] | None = None,
    depth: str = "standard",
    output_dir: str | Path = "outputs/ecommerce",
    search_fn: SearchFn | None = None,
    llm_fn: LlmFn | None = None,
    progress_callback: ProgressFn | None = None,
) -> EcommerceResearchState:
    """端到端跑一次跨境电商选品调研，并写出三类文件。

    Args:
        llm_fn: 注入的 LLM 函数，启用后 opportunity_scorer 会优先用 LLM 打分。
            默认 None（纯规则模式，不消耗 LLM 额度）。
        progress_callback: 阶段进度回调，启用后会收到 start/planner_done/research_*/scoring_done/report_done/quality_done 事件。

    Returns:
        最终 state（含 final_report / quality_check / audit_log / output_paths）。
    """
    state = create_initial_state(
        query=query,
        target_market=target_market,
        platforms=platforms,
        depth=depth,
    )

    final_state = await run_ecommerce_graph(
        state,
        search_fn=search_fn or default_search_fn,
        llm_fn=llm_fn,
        progress_callback=progress_callback,
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    slug = slugify(query)
    report_path = output_path / f"{slug}-report.md"
    audit_path = output_path / f"{slug}-audit.json"
    quality_path = output_path / f"{slug}-quality.json"

    report_path.write_text(final_state["final_report"], encoding="utf-8")
    audit_path.write_text(
        json.dumps(final_state["audit_log"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    quality_path.write_text(
        json.dumps(final_state["quality_check"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    final_state["output_paths"] = {
        "report": str(report_path),
        "audit": str(audit_path),
        "quality": str(quality_path),
    }
    return final_state
