"""
OpportunityScoringAgent：机会评分汇总（LLM 优先，规则兜底）。

【正经注释】
异步节点。汇总 trend/competitor/review 三方结果，先用注入的 llm_fn 让 LLM
对趋势/竞争/痛点/利润/风险五维打分并给出理由；LLM 不可用或解析失败时
自动退回规则评分。evidence_score 始终由证据数量客观计算，overall_score
由 schemas.scoring 的加权公式重算，保证权重一致、可解释。
scored_by 字段记录本次评分来源（llm/rule），便于审计。

【大白话注释】
把前面的研究结果收上来，先试着让大模型打分（更有判断力）；
大模型用不了就退回原来的规则打分。证据分永远按"找到了几条来源"算，
总分按固定权重算，这样每次评分口径一致、能讲清楚。
"""

from __future__ import annotations

import time

from multi_agents.ecommerce.llm_helper import LlmFn, clamp, llm_json
from multi_agents.ecommerce.prompts import OPPORTUNITY_SCORER_SYSTEM_PROMPT
from multi_agents.ecommerce.runtime.budget_manager import BudgetManager
from multi_agents.ecommerce.schemas.scoring import calculate_overall_score
from multi_agents.ecommerce.state import EcommerceResearchState

_RULE_REASONS = [
    "评分基于公开趋势、竞品和评论痛点资料。",
    "该评分是选品辅助决策，不代表真实销量预测。",
    "进入前仍需验证供应链成本、平台规则和真实广告成本。",
]


def _rule_evidence_score(state: EcommerceResearchState) -> tuple[float, int]:
    evidence_count = (
        len(state["trend_result"].get("evidence", []))
        + len(state["competitor_result"].get("evidence", []))
        + len(state["review_result"].get("evidence", []))
    )
    return min(10.0, 3.0 + evidence_count), evidence_count


def _recommendation(overall: float) -> str:
    if overall >= 7.5:
        return "建议进入，但需要先做小规模测试"
    if overall >= 6.0:
        return "建议谨慎测试进入"
    return "暂不建议进入，需补充数据验证"


def _score_from_llm(data: dict, key: str, fallback: float) -> float:
    value = data.get(key, fallback)
    try:
        return clamp(value)
    except (TypeError, ValueError):
        return fallback


async def run_opportunity_scoring(
    state: EcommerceResearchState,
    *,
    llm_fn: LlmFn | None = None,
    budget_manager: BudgetManager | None = None,
) -> EcommerceResearchState:
    started = time.perf_counter()

    # 规则基线分（来自三方结果 + 固定默认值）
    trend_score = float(state["trend_result"].get("trend_score", 4.0))
    competition_score = float(state["competitor_result"].get("competition_score", 4.0))
    pain_point_score = float(state["review_result"].get("pain_point_score", 4.0))
    margin_score = 6.0
    risk_score = 5.0
    evidence_score, evidence_count = _rule_evidence_score(state)

    # 预算闸门：LLM 预算耗尽则强制降级为规则评分，并记录降级事件。
    if llm_fn is not None and budget_manager is not None and not budget_manager.can_use("llm"):
        budget_manager.record_degradation("OpportunityScoringAgent", "llm budget exceeded")
        llm_fn = None

    # LLM 打分（可用则覆盖五维分 + 理由；evidence_score 仍走规则）
    used_llm = False
    llm_reasons: list[str] | None = None
    if llm_fn is not None:
        if budget_manager is not None:
            budget_manager.record("llm")
        user = (
            f"品类：{state['query']}（市场：{state['target_market']}）\n"
            f"趋势摘要：{state['trend_result'].get('summary', '')}\n"
            f"竞品摘要：{state['competitor_result'].get('summary', '')} "
            f"价格区间：{state['competitor_result'].get('price_range', '')}\n"
            f"用户痛点：{'; '.join(state['review_result'].get('pain_points', [])[:5]) or '数据不足'}\n\n"
            "请基于以上信息，对这条品类的跨境电商选品机会打分。"
            "只返回一个 JSON 对象，不要任何解释：\n"
            '{"trend_score":0-10,"competition_score":0-10(分越高代表越容易切入),'
            '"pain_point_score":0-10,"margin_score":0-10,"risk_score":0-10,'
            '"reasons":["用中文给出2-4条打分理由"]}'
        )
        data, used_llm = await llm_json(llm_fn, OPPORTUNITY_SCORER_SYSTEM_PROMPT, user)
        if used_llm and data:
            trend_score = _score_from_llm(data, "trend_score", trend_score)
            competition_score = _score_from_llm(
                data, "competition_score", competition_score
            )
            pain_point_score = _score_from_llm(
                data, "pain_point_score", pain_point_score
            )
            margin_score = _score_from_llm(data, "margin_score", margin_score)
            risk_score = _score_from_llm(data, "risk_score", risk_score)
            if isinstance(data.get("reasons"), list):
                llm_reasons = [str(r) for r in data["reasons"] if r][:5]

    overall_score = calculate_overall_score(
        trend_score=trend_score,
        competition_score=competition_score,
        pain_point_score=pain_point_score,
        margin_score=margin_score,
        risk_score=risk_score,
        evidence_score=evidence_score,
    )
    reasons = llm_reasons or _RULE_REASONS

    state["opportunity_score"] = {
        "trend_score": trend_score,
        "competition_score": competition_score,
        "pain_point_score": pain_point_score,
        "margin_score": margin_score,
        "risk_score": risk_score,
        "evidence_score": evidence_score,
        "overall_score": overall_score,
        "recommendation": _recommendation(overall_score),
        "reasons": reasons,
        "scored_by": "llm" if used_llm else "rule",
    }

    warning = "llm scoring unavailable, fallback to rule" if (llm_fn is not None and not used_llm) else None
    state["audit_log"].append(
        {
            "agent": "OpportunityScoringAgent",
            "status": "success",
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": evidence_count,
            "confidence": round(min(0.9, 0.3 + evidence_count * 0.08), 2),
            "warning": warning,
        }
    )
    return state
