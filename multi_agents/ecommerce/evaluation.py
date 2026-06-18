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

from multi_agents.ecommerce.runtime.telemetry import summarize_governance


def build_evaluation_summary(state: dict) -> dict:
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
    return summary
