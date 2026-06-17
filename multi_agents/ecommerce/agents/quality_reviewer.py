"""
QualityReviewerAgent：报告质量检查。

【正经注释】
同步节点。对最终报告做多维度质量评估：
- citation_coverage：报告含有的 http(s) 引用数 / 基准
- evidence_sufficiency：三方 evidence 总数 / 基准
- logic_consistency：暂以固定基线（可后续替换为 LLM 交叉校验）
- risk_disclosure：报告是否同时包含"风险"与"销量预测"字样
- 过度确定性：扫描"稳赚/必爆"等违规表述
产出 issues 列表与 passed 标志。

【大白话注释】
报告写完后做体检：引用够不够、证据够不够、有没有写风险提示、
有没有乱说"稳赚必爆"。有问题就记下来。
"""

from __future__ import annotations

import time

from multi_agents.ecommerce.state import EcommerceResearchState

OVERCONFIDENT_TERMS = ["稳赚", "必爆", "一定增长", "没有风险", "保证成功"]

# 质量基准
_CITATION_BENCHMARK = 3
_EVIDENCE_BENCHMARK = 6


def run_quality_review(state: EcommerceResearchState) -> EcommerceResearchState:
    started = time.perf_counter()
    report = state.get("final_report", "")

    evidence_count = (
        len(state["trend_result"].get("evidence", []))
        + len(state["competitor_result"].get("evidence", []))
        + len(state["review_result"].get("evidence", []))
    )
    citation_count = report.count("https://") + report.count("http://")
    citation_coverage = round(min(1.0, citation_count / _CITATION_BENCHMARK), 2)
    evidence_sufficiency = round(min(1.0, evidence_count / _EVIDENCE_BENCHMARK), 2)
    risk_disclosure = "风险" in report and "销量预测" in report
    overconfident = [term for term in OVERCONFIDENT_TERMS if term in report]

    issues: list[str] = []
    if citation_coverage < 0.5:
        issues.append("引用覆盖率偏低")
    if evidence_sufficiency < 0.5:
        issues.append("证据来源数量偏少")
    if not risk_disclosure:
        issues.append("风险披露不足")
    if overconfident:
        issues.append(f"存在过度确定性表达：{', '.join(overconfident)}")

    state["quality_check"] = {
        "passed": not issues,
        "citation_coverage": citation_coverage,
        "evidence_sufficiency": evidence_sufficiency,
        "logic_consistency": 0.8,
        "risk_disclosure": risk_disclosure,
        "issues": issues,
    }

    state["audit_log"].append(
        {
            "agent": "QualityReviewerAgent",
            "status": "success" if not issues else "partial",
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": evidence_count,
            "confidence": 0.8,
            "warning": "; ".join(issues) if issues else None,
        }
    )
    return state
