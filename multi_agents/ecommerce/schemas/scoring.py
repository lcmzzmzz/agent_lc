"""
机会评分（Opportunity Scoring）的数值工具。

【正经注释】
将 6 个维度的 0-10 分按加权平均汇总为 overall_score。
权重之和为 1.0，体现各维度对选品决策的相对重要性。
所有单项分数都会先经 clamp_score 限制在 [0, 10]。

【大白话注释】
就是把趋势、竞争、痛点、利润、风险、证据这几项打分，
按"谁更重要"配个权重，最后算出一个总分。
"""

from __future__ import annotations


def clamp_score(value: float | int) -> float:
    """把分数限制在 [0, 10]。"""
    return float(max(0.0, min(10.0, value)))


# 各维度权重，和为 1.0
_SCORE_WEIGHTS = {
    "trend_score": 0.22,
    "competition_score": 0.18,
    "pain_point_score": 0.22,
    "margin_score": 0.14,
    "risk_score": 0.10,
    "evidence_score": 0.14,
}


def calculate_overall_score(
    *,
    trend_score: float,
    competition_score: float,
    pain_point_score: float,
    margin_score: float,
    risk_score: float,
    evidence_score: float,
) -> float:
    """按权重计算加权总分，保留两位小数。"""
    raw = (
        clamp_score(trend_score) * _SCORE_WEIGHTS["trend_score"]
        + clamp_score(competition_score) * _SCORE_WEIGHTS["competition_score"]
        + clamp_score(pain_point_score) * _SCORE_WEIGHTS["pain_point_score"]
        + clamp_score(margin_score) * _SCORE_WEIGHTS["margin_score"]
        + clamp_score(risk_score) * _SCORE_WEIGHTS["risk_score"]
        + clamp_score(evidence_score) * _SCORE_WEIGHTS["evidence_score"]
    )
    return round(raw, 2)
