"""
TrendResearchAgent：市场趋势研究（summary 已 LLM 化）。

【正经注释】
异步节点。消费 research_plan.trend_queries，检索后把标准化数据源的 snippet/content
拼接喂给 llm_fn，让 LLM 基于真实资料生成中文趋势 summary；LLM 不可用则回退模板。
trend_score 仍按数据源数量客观计算，evidence 保留来源。失败走 fallback，不中断流程。

【大白话注释】
搜趋势资料，把搜到的内容喂给大模型让它写一段中文趋势总结；
大模型用不了就用原来的固定模板。分数还是按"搜到几条"算。
"""

from __future__ import annotations

import logging
import time

from multi_agents.ecommerce.config import get_depth_config
from multi_agents.ecommerce.agents.content_scoring import (
    coerce_confidence,
    coerce_score,
    coerce_string_list,
    format_sources_for_prompt,
    rule_rationale,
    source_count_confidence,
)
from multi_agents.ecommerce.llm_helper import LlmFn, llm_json
from multi_agents.ecommerce.prompts import TREND_RESEARCHER_SYSTEM_PROMPT
from multi_agents.ecommerce.state import EcommerceResearchState
from multi_agents.ecommerce.tools.product_search import SearchFn, search_sources
from multi_agents.ecommerce.agents.audit import finalize_audit

logger = logging.getLogger(__name__)

_RESULTS_PER_QUERY = 3  # 每条 trend_query 检索取 3 条结果（search_sources 内部去重）
_TEMPLATE_SUMMARY = "{query} 在 {market} 市场存在可调研需求信号。"  # LLM 不可用时的固定模板 summary


async def _llm_trend_score(
    llm_fn: LlmFn | None, query: str, market: str, sources: list
) -> tuple[dict | None, bool]:
    """用 LLM 基于检索资料生成结构化趋势评分；不可用返回 (None, False)。"""
    if not llm_fn or not sources:        # 没传 LLM 或没搜到资料 → 直接返回 None（走模板）
        return None, False
    text = format_sources_for_prompt(sources)
    user = (
        f"品类：{query}（市场：{market}）\n"
        f"以下是与该品类市场趋势相关的公开资料：\n{text}\n"
        "请只返回 JSON 对象："
        '{"summary":"2-4句中文总结","trend_score":0-10,"confidence":0-0.9,'
        '"key_findings":["中文发现"],"negative_signals":["中文负面信号"],'
        '"scoring_rationale":"中文评分理由"}。'
        "trend_score 只评价市场趋势强弱，不评价竞争、利润或进入难度。"
        "如果资料主要显示需求下降、负面报道或增长乏力，请降低 trend_score。"
        "如果证据稀疏、矛盾或相关性弱，请降低 confidence。"
    )
    return await llm_json(llm_fn, TREND_RESEARCHER_SYSTEM_PROMPT, user)


async def run_trend_research(
    state: EcommerceResearchState,
    *,                                # keyword-only 分隔符：search_fn/llm_fn 调用时必须用关键字传（防传串）
    search_fn: SearchFn,              # 检索函数（graph 注入的 branch_search_fn，带预算闸门）—— 能力注入，不进 state
    llm_fn: LlmFn | None = None,      # LLM 函数（None=不调 LLM，summary 走模板；生产传 default_llm_fn）
) -> EcommerceResearchState:
    """市场趋势研究（异步，LLM 优先）。

    【正经注释】
    异步 agent 函数，被 graph 的 trend_node 经 _research_node 模板调用（guard 包超时）。
    消费 research_plan.trend_queries 逐条检索 → 标准化去重 → 截断到 max_sources_per_agent；
    trend_score 按"搜到几条"客观算（>=3 给 7.0，否则 5.5），confidence 随条数递增（封顶 0.9）；
    summary 优先用 LLM 基于真实资料写中文，LLM 不可用回退模板。
    任何异常都走低分兜底（trend_score=4.0/confidence=0.2），不向上抛——graph 的 guard 容错
    和这里的 try/except 是双层保险（guard 兜超时/重试，这里兜业务异常）。

    【大白话注释】
    趋势这一路干活的函数（trend_node 的真身）。拿 planner 给的查询词去搜，搜到的资料喂
    大模型写中文总结；大模型用不了就用固定模板凑一句。分数纯看搜到几条（≥3 条算有信号）。
    搜炸了就给低分兜底，记一笔错，不让整个流程挂。
    """
    started = time.perf_counter()                              # 计时起点：finalize_audit 据此算 duration_ms
    config = get_depth_config(state["depth"])                  # 取 depth 档配置（fast/standard/deep → max_sources_per_agent 等）
    queries = state["research_plan"].get("trend_queries", [])  # 读 planner 产的趋势查询清单（本路的输入契约）
    logger.info(f"[Trend] 开始 query='{state['query']}' queries={len(queries)}")

    try:
        # ① 检索：逐条 query 调 search_fn（每条取 _RESULTS_PER_QUERY=3 条）、标准化、url 去重
        sources = await search_sources(
            queries=queries,
            search_fn=search_fn,
            max_results_per_query=_RESULTS_PER_QUERY,
        )
        limited_sources = sources[: config["max_sources_per_agent"]]  # ② 截断到本档上限（fast/standard/deep 不同）
        source_count = len(limited_sources)                    # 实际拿到的有效来源条数（算分依据）
        # ③ 结构化评分：LLM 成功时采用内容评分；不可用或 JSON 无效时回退规则评分
        rule_confidence = source_count_confidence(source_count)
        rule_trend_score = 7.0 if source_count >= 3 else 5.5

        llm_data, used_llm = await _llm_trend_score(
            llm_fn, state["query"], state["target_market"], limited_sources
        )
        if llm_fn and not used_llm:                         # 传了 LLM 却没拿到 JSON → 记 warning（说明 LLM 调失败或返回格式无效）
            logger.warning("[Trend] LLM scoring 失败，回退规则评分")

        summary = (
            str(llm_data.get("summary")).strip()
            if used_llm and llm_data and llm_data.get("summary")
            else _TEMPLATE_SUMMARY.format(
                query=state["query"], market=state["target_market"]
            )
        )
        trend_score = (
            coerce_score(llm_data, "trend_score", rule_trend_score)
            if used_llm
            else rule_trend_score
        )
        confidence = (
            coerce_confidence(llm_data, rule_confidence)
            if used_llm
            else rule_confidence
        )
        key_findings = (
            coerce_string_list(llm_data.get("key_findings"), limit=5)
            if used_llm and llm_data
            else [
                "公开资料显示该品类存在搜索和评测内容。",
                "需要结合平台真实销量和供应链成本进一步验证。",
            ]
        )
        negative_signals = (
            coerce_string_list(llm_data.get("negative_signals"), limit=5)
            if used_llm and llm_data
            else []
        )
        scoring_rationale = (
            str(llm_data.get("scoring_rationale")).strip()
            if used_llm and llm_data and llm_data.get("scoring_rationale")
            else rule_rationale("trend_score")
        )

        # ⑤ 写 trend_result（本路产出）：summary/来源/分数/发现/证据/置信度
        state["trend_result"] = {
            "summary": summary,
            "summary_source": "llm" if used_llm else "template",  # 标记 summary 是 LLM 写的还是模板（scoring/报告会读）
            "trend_score": trend_score,
            "key_findings": key_findings,
            "negative_signals": negative_signals,
            "scoring_rationale": scoring_rationale,
            "scored_by": "llm" if used_llm else "rule",
            "evidence": limited_sources,                        # 保留来源（报告引用 + quality 算引用覆盖都要用）
            "confidence": confidence,
        }
        # ⑥ 状态判定：≥2 条算 success，否则 partial（数据不足）
        status = "success" if source_count >= 2 else "partial"
        warning = None if source_count >= 2 else "trend source data limited"
        logger.info(
            f"[Trend] 完成 status={status} summary_source={state['trend_result']['summary_source']}"
        )
    except Exception as exc:
        # ⚠️ 业务异常兜底（检索/处理炸了）：给低分（4.0 < 正常 5.5）+ 低置信（0.2），
        #   让下游 scoring 诚实降分；不向上抛（graph 还有一层 guard，这里是业务层保险）。
        #   注意：graph 的 _failed_child_state 给 2.0（guard 层失败），这里给 4.0（agent 内部失败），两层兜底分数不同。
        logger.error(f"[Trend] 失败: {exc}", exc_info=True)
        state["trend_result"] = {
            "summary": _TEMPLATE_SUMMARY.format(
                query=state["query"], market=state["target_market"]
            ),
            "summary_source": "template",
            "trend_score": 4.0,                                 # 兜底分：比正常 5.5 还低，标记"数据源失败"
            "key_findings": [],
            "negative_signals": [],
            "scoring_rationale": "Trend research failed before content scoring.",
            "scored_by": "rule",
            "evidence": [],                                     # 没拿到证据
            "confidence": 0.2,                                  # 极低置信：基本不可信
            "error": str(exc),                                  # 留错误信息便于排查
        }
        state["errors"].append({"agent": "TrendResearchAgent", "error": str(exc)})  # 记进 errors（graph 的 reducer 会汇总）
        status = "partial"
        warning = "trend research failed"

    # ⑦ 统一记审计（成功/失败都走这）：duration_ms 由 started 算；source_count 用 evidence 长度
    #    （失败分支 evidence=[] → source_count=0，所以这里不直接用上面的 source_count 变量）
    finalize_audit(
        state,
        "TrendResearchAgent",
        status=status,
        source_count=len(state["trend_result"].get("evidence", [])),
        confidence=state["trend_result"].get("confidence", 0.0),
        warning=warning,
        started=started,
    )
    return state
