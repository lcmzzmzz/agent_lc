"""
OpportunityScoringAgent：机会评分汇总。

【正经注释】
同步节点。汇总 trend/competitor/review 三方结果与证据数量，
调用 schemas.scoring.calculate_overall_score 生成 6 维加权总分与 overall_score，
并给出"是否建议进入"的分级结论。评分是辅助决策，不是销量预测。

【大白话注释】
把前面趋势、竞品、评论的分数收上来，按权重算个总分，
再根据总分高低给一句"建议进入/谨慎测试/暂不建议"。
"""

from __future__ import annotations

import time

from multi_agents.ecommerce.schemas.scoring import calculate_overall_score
from multi_agents.ecommerce.state import EcommerceResearchState


def run_opportunity_scoring(state: EcommerceResearchState) -> EcommerceResearchState:
    started = time.perf_counter()

    trend_score = float(state["trend_result"].get("trend_score", 4.0))
    competition_score = float(state["competitor_result"].get("competition_score", 4.0))
    pain_point_score = float(state["review_result"].get("pain_point_score", 4.0))

    evidence_count = (
        len(state["trend_result"].get("evidence", []))
        + len(state["competitor_result"].get("evidence", []))
        + len(state["review_result"].get("evidence", []))
    )
    evidence_score = min(10.0, 3.0 + evidence_count)
    margin_score = 6.0
    risk_score = 5.0

    overall_score = calculate_overall_score(
        trend_score=trend_score,
        competition_score=competition_score,
        pain_point_score=pain_point_score,
        margin_score=margin_score,
        risk_score=risk_score,
        evidence_score=evidence_score,
    )

    if overall_score >= 7.5:
        recommendation = "建议进入，但需要先做小规模测试"
    elif overall_score >= 6.0:
        recommendation = "建议谨慎测试进入"
    else:
        recommendation = "暂不建议进入，需补充数据验证"

    state["opportunity_score"] = {
        "trend_score": trend_score,
        "competition_score": competition_score,
        "pain_point_score": pain_point_score,
        "margin_score": margin_score,
        "risk_score": risk_score,
        "evidence_score": evidence_score,
        "overall_score": overall_score,
        "recommendation": recommendation,
        "reasons": [
            "评分基于公开趋势、竞品和评论痛点资料。",
            "该评分是选品辅助决策，不代表真实销量预测。",
            "进入前仍需验证供应链成本、平台规则和真实广告成本。",
        ],
    }

    state["audit_log"].append(
        {
            "agent": "OpportunityScoringAgent",
            "status": "success",
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": evidence_count,
            "confidence": round(min(0.9, 0.3 + evidence_count * 0.08), 2),
            "warning": None,
        }
    )
    return state
