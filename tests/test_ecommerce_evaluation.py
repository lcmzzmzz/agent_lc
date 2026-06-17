"""EcomResearcher 评估摘要层单测。"""

from multi_agents.ecommerce.evaluation import build_evaluation_summary

# 构造一个合成 state，使各项指标可精确断言：
# - 3 条研究 evidence（trend/competitor/review 各 3）= 9
# - research_entries（非 Quality）confidence = [0.8, 0.7, 0.78] -> fmean 0.76
# - 1 条 partial（Review）-> fallback_count 1
# - duration 总和 500+400+600+320 = 1820
# - overall_score 7.8
_FAKE_STATE = {
    "opportunity_score": {
        "overall_score": 7.8,
        "recommendation": "建议谨慎测试进入",
        "scored_by": "llm",
    },
    "quality_check": {"passed": True},
    "audit_log": [
        {"agent": "TrendResearchAgent", "status": "success", "confidence": 0.8, "duration_ms": 500},
        {"agent": "CompetitorAnalysisAgent", "status": "success", "confidence": 0.7, "duration_ms": 400},
        {"agent": "ReviewInsightAgent", "status": "partial", "confidence": 0.78, "duration_ms": 600},
        {"agent": "QualityReviewerAgent", "status": "success", "confidence": 0.9, "duration_ms": 320},
    ],
    "trend_result": {"evidence": [{"url": "a"}, {"url": "b"}, {"url": "c"}]},
    "competitor_result": {"evidence": [{"url": "d"}, {"url": "e"}, {"url": "f"}]},
    "review_result": {"evidence": [{"url": "g"}, {"url": "h"}, {"url": "i"}]},
}


def test_build_evaluation_summary_counts_metrics():
    summary = build_evaluation_summary(_FAKE_STATE)

    assert summary["overall_score"] == 7.8
    assert summary["confidence"] == 0.76
    assert summary["evidence_count"] == 9
    assert summary["fallback_count"] == 1
    assert summary["duration_ms"] == 1820
    assert summary["scored_by"] == "llm"
    assert summary["quality_passed"] is True


def test_build_evaluation_summary_handles_empty_state():
    summary = build_evaluation_summary({})

    assert summary["overall_score"] == 0.0
    assert summary["confidence"] == 0.0
    assert summary["evidence_count"] == 0
    assert summary["fallback_count"] == 0
    assert summary["duration_ms"] == 0
    assert summary["scored_by"] == "rule"
    assert summary["quality_passed"] is False
