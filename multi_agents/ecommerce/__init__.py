"""
EcomResearcher：跨境电商 AI 选品与市场调研助手。

【正经注释】
本包是基于 GPT Researcher / LangGraph 的垂直领域多 Agent 工作流，
聚焦跨境电商选品与市场调研场景，实现从品类输入到结构化选品报告的自动化闭环。

【大白话注释】
这个包是"跨境电商选品助手"。给它一个品类关键词，它会自动做趋势、竞品、
评论痛点分析，打分，最后输出一份选品报告 + 质量检查 + 执行日志。
"""

# 注意：run_ecommerce_research 在 runner.py（Task 5）就绪后，再在此处导出，
# 避免依赖链未完成时 import 整个包失败。
# 当前可独立导入的入口：from multi_agents.ecommerce.state import create_initial_state

__all__: list[str] = []
