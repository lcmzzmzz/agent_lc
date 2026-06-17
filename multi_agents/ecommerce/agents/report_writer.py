"""
EcommerceReportWriterAgent：选品报告生成。

【正经注释】
同步节点。按 schemas.report.REPORT_SECTIONS 的固定章节顺序，把趋势/竞品/评论/
评分/风险拼成 Markdown 报告。引用来自三方 evidence 的 url，去重后编号列出。
第 7 节强制包含"风险"与"销量预测"字样，供 QualityReviewerAgent 验证风险披露。

【大白话注释】
把前面所有人写进小本本的内容，按固定章节拼成一份报告。
最后把用到的网址列出来当参考文献。报告里必须写风险提示。
"""

from __future__ import annotations

import time

from multi_agents.ecommerce.schemas.report import build_report_title
from multi_agents.ecommerce.state import EcommerceResearchState, EcommerceSource


def collect_citation_lines(state: EcommerceResearchState) -> list[str]:
    """从三方 evidence 收集去重引用行。"""
    sources: list[EcommerceSource] = []
    for result_key in ("trend_result", "competitor_result", "review_result"):
        sources.extend(state[result_key].get("evidence", []))

    lines: list[str] = []
    seen: set[str] = set()
    index = 0
    for source in sources:
        url = source.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        index += 1
        title = source.get("title", "Source")
        lines.append(f"{index}. [{title}]({url})")
    return lines or ["暂无可用引用，需补充数据源。"]


def run_report_writer(state: EcommerceResearchState) -> EcommerceResearchState:
    started = time.perf_counter()
    score = state["opportunity_score"]
    review = state["review_result"]
    competitor = state["competitor_result"]

    pain_points = review.get("pain_points", [])
    section_4 = (
        "## 4. 用户痛点与差评洞察\n" + "\n".join(f"- {item}" for item in pain_points)
        if pain_points
        else "## 4. 用户痛点与差评洞察\n评论痛点数据不足，建议补充真实平台评论。"
    )

    section_5_items = review.get("opportunity_insights", []) + competitor.get(
        "differentiation_opportunities", []
    )
    section_5 = "## 5. 差异化机会\n" + "\n".join(
        f"- {item}" for item in section_5_items
    )

    report = "\n\n".join(
        [
            build_report_title(state["query"], state["target_market"]),
            "## 1. 选品结论\n"
            f"{score.get('recommendation', '需补充数据后再判断')}。"
            "本报告基于公开资料生成，结论仅用于选品前期调研。",
            "## 2. 市场趋势分析\n"
            f"{state['trend_result'].get('summary', '趋势数据不足。')}",
            "## 3. 竞品格局分析\n"
            f"{competitor.get('summary', '竞品数据不足。')}\n\n"
            f"初步价格区间：{competitor.get('price_range', 'unknown')}",
            section_4,
            section_5,
            "## 6. 价格区间与利润空间初步判断\n"
            "当前版本仅根据公开竞品价格做初步判断，不包含供应链、物流、广告和退货成本。",
            "## 7. 风险因素\n"
            "- 公开数据可能不完整。\n"
            "- 平台评论和搜索结果存在样本偏差。\n"
            "- 真实利润需结合采购、物流、广告和售后成本验证。\n"
            "- 不应将本报告结论视为销量预测。",
            "## 8. 机会评分\n"
            f"- 总分：{score.get('overall_score', 0)} / 10\n"
            f"- 趋势分：{score.get('trend_score', 0)}\n"
            f"- 竞争分：{score.get('competition_score', 0)}\n"
            f"- 痛点分：{score.get('pain_point_score', 0)}\n"
            f"- 证据充分度：{score.get('evidence_score', 0)}",
            "## 9. 是否建议进入\n"
            f"{score.get('recommendation', '暂不建议进入，需补充数据验证')}",
            "## 10. 数据来源与引用\n" + "\n".join(collect_citation_lines(state)),
        ]
    )

    state["final_report"] = report
    state["audit_log"].append(
        {
            "agent": "EcommerceReportWriterAgent",
            "status": "success",
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "source_count": len(collect_citation_lines(state)),
            "confidence": 0.8,
            "warning": None,
        }
    )
    return state
