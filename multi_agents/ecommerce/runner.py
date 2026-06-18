"""
EcomResearcher 运行入口与文件输出（含按次全链路日志文件）。

【正经注释】
run_ecommerce_research 是对外统一入口：构造初始状态 → 跑完整 graph →
把报告 / 审计日志 / 质量检查分别写成 .md / .json 文件。
每次研究还会在 logs/ecommerce/ 下创建一个独立 log 文件，文件名为
<时间戳>_<关键词>.log，绑定到 multi_agents.ecommerce logger，
捕获整条链路（graph 阶段 / 各 Agent / LLM 调用）的 INFO/WARNING/ERROR，
便于事后排查。default_search_fn 复用 GPT Researcher 默认检索器，失败降级为空结果。

【大白话注释】
一键启动按钮：输入品类，跑完整条流程，存报告/日志/质检三类文件。
另外每次跑都会单独生成一个日志文件（名字是"时间+关键词"），
全程每一步都记进去，出问题能回看。
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from multi_agents.ecommerce.evaluation import build_evaluation_summary
from multi_agents.ecommerce.graph import ProgressFn, run_ecommerce_graph
from multi_agents.ecommerce.llm_helper import LlmFn
from multi_agents.ecommerce.runtime.policy_guard import (
    PolicyViolation,
    validate_research_request,
)
from multi_agents.ecommerce.state import EcommerceResearchState, create_initial_state
from multi_agents.ecommerce.tools.product_search import SearchFn

# 全链路日志统一走这个 logger；各子模块 logger 会 propagate 到这里
logger = logging.getLogger("multi_agents.ecommerce")

_SLUG_RE = re.compile(r"[^\w]+", flags=re.UNICODE)
_LOG_FORMAT = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")


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
            logger.warning(f"[search] 默认检索失败 query='{query}': {exc}")
            return []

    return await asyncio.to_thread(_sync_search)


def _setup_run_log(query: str) -> tuple[logging.FileHandler, Path]:
    """为本次研究创建独立 log 文件 handler，文件名 = 时间戳_关键词.log。"""
    log_dir = Path("logs/ecommerce")
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{ts}_{slugify(query)}.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(_LOG_FORMAT)
    ecommerce_logger = logging.getLogger("multi_agents.ecommerce")
    ecommerce_logger.addHandler(handler)
    # 确保该 logger 不会因自身 level 过滤掉 INFO
    if ecommerce_logger.level == logging.NOTSET or ecommerce_logger.level > logging.INFO:
        ecommerce_logger.setLevel(logging.INFO)
    return handler, log_path


def _teardown_run_log(handler: logging.FileHandler) -> None:
    ecommerce_logger = logging.getLogger("multi_agents.ecommerce")
    ecommerce_logger.removeHandler(handler)
    handler.flush()
    handler.close()


def _resolve_search_fn(search_fn: SearchFn | None) -> SearchFn:
    """按 ECOMMERCE_SEARCH_BACKEND 选择检索源：apify 或默认 tavily。

    - 显式传入 search_fn 优先（测试/程序化用）
    - ECOMMERCE_SEARCH_BACKEND=apify 且 APIFY_API_TOKEN 已配 → Apify
    - 否则 → Tavily（默认检索器）
    """
    if search_fn is not None:
        return search_fn
    backend = os.environ.get("ECOMMERCE_SEARCH_BACKEND", "tavily").strip().lower()
    if backend == "apify":
        try:
            from multi_agents.ecommerce.tools.apify_search import make_apify_search_fn

            logger.info("[runner] 检索源: Apify")
            return make_apify_search_fn()
        except Exception as exc:
            logger.warning(f"[runner] Apify 不可用({exc})，回退 Tavily")
    return default_search_fn


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
    """端到端跑一次跨境电商选品调研，并写出报告/审计/质检/log 文件。"""
    handler, log_path = _setup_run_log(query)
    logger.info(
        f"========== 开始研究 query='{query}' market={target_market} "
        f"depth={depth} platforms={platforms or ['amazon','google']} =========="
    )
    try:
        validate_research_request(
            query=query,
            target_market=target_market,
            platforms=platforms or ["amazon", "google"],
            depth=depth,
        )
    except PolicyViolation as exc:
        _teardown_run_log(handler)
        raise ValueError(str(exc)) from exc
    try:
        state = create_initial_state(
            query=query,
            target_market=target_market,
            platforms=platforms,
            depth=depth,
        )
        final_state = await run_ecommerce_graph(
            state,
            search_fn=_resolve_search_fn(search_fn),
            llm_fn=llm_fn,
            progress_callback=progress_callback,
        )
    finally:
        logger.info(f"========== 研究结束，日志见 {log_path} ==========")
        _teardown_run_log(handler)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    slug = slugify(query)
    report_path = output_path / f"{slug}-report.md"
    audit_path = output_path / f"{slug}-audit.json"
    quality_path = output_path / f"{slug}-quality.json"
    evaluation_path = output_path / f"{slug}-evaluation.json"

    report_path.write_text(final_state["final_report"], encoding="utf-8")
    audit_path.write_text(
        json.dumps(final_state["audit_log"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    quality_path.write_text(
        json.dumps(final_state["quality_check"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    evaluation_summary = build_evaluation_summary(final_state)
    evaluation_path.write_text(
        json.dumps(evaluation_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    final_state["evaluation_summary"] = evaluation_summary

    final_state["output_paths"] = {
        "report": str(report_path),
        "audit": str(audit_path),
        "quality": str(quality_path),
        "evaluation": str(evaluation_path),
        "log": str(log_path),
    }
    return final_state
