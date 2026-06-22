"""
EcomResearcher 评估摘要层。

【正经注释】
build_evaluation_summary 从一次研究的最终 state 抽取稳定、可比较的指标：
总分、平均置信度、证据数量、降级次数、总耗时、是否质检通过、评分方式。
供 runner 写 evaluation.json、demo 导出、评估对比页统一消费。

【大白话注释】
把一次研究的结果"浓缩"成几个关键数字（打多少分、多可信、用了几条证据、
有没有降级、跑了多久），方便横向比较多次研究，也能直接放进简历讲。
"""

from __future__ import annotations

from statistics import fmean
from typing import Any, Mapping

from multi_agents.ecommerce.runtime.telemetry import summarize_governance
from multi_agents.ecommerce.runtime.trace_recorder import summarize_trace


def _summarize_human_review(review: Mapping[str, Any] | None) -> dict[str, Any]:
    """把人工评审（HITL）结构压缩成几个可比较的计数指标。

    【正经注释】无评审或字段缺失时返回零值；有评审则统计：评审状态、被覆盖的分数项数、
    被标记为 irrelevant/weak 的证据数、报告级标签数。
    【大白话注释】把"人改了哪些东西"数一数：改了几个分数、否了几条证据、贴了几个报告标签。
    """
    if not review:
        return {
            "human_review_status": "none",
            "human_overridden_score_count": 0,
            "human_irrelevant_source_count": 0,
            "human_weak_source_count": 0,
            "human_report_label_count": 0,
        }
    labels = review.get("evidence_labels", [])
    return {
        "human_review_status": review.get("review_status", "pending"),
        "human_overridden_score_count": len(review.get("score_overrides", {})),
        "human_irrelevant_source_count": sum(
            1 for row in labels if row.get("label") == "irrelevant"
        ),
        "human_weak_source_count": sum(
            1 for row in labels if row.get("label") == "weak"
        ),
        "human_report_label_count": len(review.get("report_labels", [])),
    }


def _summarize_eval_result(eval_result: Mapping[str, Any] | None) -> dict[str, Any]:
    """抽取评估结果（passed / score），无值时返回 None/0.0 兜底。"""
    if not eval_result:
        return {"eval_passed": None, "eval_score": 0.0}
    return {
        "eval_passed": eval_result.get("passed"),
        "eval_score": float(eval_result.get("score", 0.0)),
    }


def _summarize_mcp_context(mcp_context: Mapping[str, Any] | None) -> dict[str, Any]:
    """抽取 MCP 工具调用上下文：是否启用、总调用数、失败调用数。

    【正经注释】status 不在 {"success","ok"} 视为失败。
    【大白话注释】数一下 MCP 工具调了几次、挂了几次。
    """
    if not mcp_context:
        return {
            "mcp_enabled": False,
            "mcp_tool_call_count": 0,
            "mcp_failed_tool_call_count": 0,
        }
    calls = mcp_context.get("tool_calls", [])
    return {
        "mcp_enabled": bool(mcp_context.get("enabled", False)),
        "mcp_tool_call_count": len(calls),
        "mcp_failed_tool_call_count": sum(
            1 for row in calls if row.get("status") not in {"success", "ok"}
        ),
    }


def build_evaluation_summary(state: Mapping[str, Any]) -> dict:
    """从最终 state 构造评估摘要。"""
    audit_log = state.get("audit_log", [])
    # 研究类节点（排除质量审查，因为它是事后检查，不算研究置信度）
    research_entries = [
        row for row in audit_log if row.get("agent") != "QualityReviewerAgent"
    ]
    evidence_count = (
        len(state.get("trend_result", {}).get("evidence", []))
        + len(state.get("competitor_result", {}).get("evidence", []))
        + len(state.get("review_result", {}).get("evidence", []))
    )
    fallback_count = sum(1 for row in audit_log if row.get("status") != "success")
    confidence_values = [
        row.get("confidence", 0.0)
        for row in research_entries
        if row.get("confidence") is not None
    ]
    confidence = round(fmean(confidence_values), 2) if confidence_values else 0.0
    duration_ms = sum(int(row.get("duration_ms", 0)) for row in audit_log)
    score = state.get("opportunity_score", {})
    review = state.get("review_result", {})
    governance_summary = summarize_governance(state.get("governance"))
    # 【正经注释】governance 自身也带 fallback_count（来自 governance.events），
    # 与 audit_log 推断出的 fallback_count 取最大值，避免 .update() 把合并值覆盖回 0。
    # 【大白话注释】两处 fallback 数各有来源，取大的那个；merge 时要先把 governance
    # 里的 fallback_count 摘出来，不然 update 会把上面算好的值又盖掉。
    governance_fallback_count = governance_summary.pop("fallback_count")
    summary = {
        "overall_score": score.get("overall_score", 0.0),
        "confidence": confidence,
        "evidence_count": evidence_count,
        "fallback_count": max(fallback_count, governance_fallback_count),
        "duration_ms": duration_ms,
        "recommendation": score.get("recommendation", ""),
        "scored_by": score.get("scored_by", "rule"),
        "quality_passed": state.get("quality_check", {}).get("passed", False),
        "review_source": review.get("review_source", "unknown"),
        "review_count": review.get("review_count", 0),
    }
    summary.update(governance_summary)
    # 【正经注释】追加上层观测指标：run_id、trace 摘要、人工评审、评估结果、MCP 工具调用。
    # 【大白话注释】把"这次跑了啥/人改了啥/MCP 挂没挂"几个数字也塞进摘要。
    summary["run_id"] = state.get("run_id", "")
    summary.update(summarize_trace(state.get("agent_trace", [])))
    summary.update(_summarize_human_review(state.get("human_review")))
    summary.update(_summarize_eval_result(state.get("eval_result")))
    summary.update(_summarize_mcp_context(state.get("mcp_context")))
    return summary
