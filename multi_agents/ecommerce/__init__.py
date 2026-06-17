"""
EcomResearcher：跨境电商 AI 选品与市场调研助手。

【正经注释】
本包是基于 GPT Researcher / LangGraph 的垂直领域多 Agent 工作流，
聚焦跨境电商选品与市场调研场景，实现从品类输入到结构化选品报告的自动化闭环。

【大白话注释】
这个包是"跨境电商选品助手"。给它一个品类关键词，它会自动做趋势、竞品、
评论痛点分析，打分，最后输出一份选品报告 + 质量检查 + 执行日志。
"""

from multi_agents.ecommerce.runner import run_ecommerce_research

__all__ = ["run_ecommerce_research"]
