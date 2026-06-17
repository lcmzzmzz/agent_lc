"""
报告结构定义。

【正经注释】
集中维护选品报告的固定章节顺序与标题构造逻辑，
保证 EcommerceReportWriterAgent 产出的报告结构稳定、可被质量检查验证。

【大白话注释】
报告写哪几章、标题怎么拼，都在这里定死，免得每次写报告章节顺序乱掉。
"""

from __future__ import annotations

REPORT_SECTIONS = [
    "选品结论",
    "市场趋势分析",
    "竞品格局分析",
    "用户痛点与差评洞察",
    "差异化机会",
    "价格区间与利润空间初步判断",
    "风险因素",
    "机会评分",
    "是否建议进入",
    "数据来源与引用",
]


def build_report_title(query: str, target_market: str) -> str:
    """构造报告一级标题。"""
    return f"# 跨境电商选品调研报告：{query}（{target_market}）"
