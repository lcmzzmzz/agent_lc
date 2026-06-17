"""GPT Researcher actions 模块
【正经注释】本模块统一导出所有 actions 子模块的公共接口，供其他模块引用。
【大白话注释】这个文件就是 actions 文件夹的"目录"——把所有工具函数的名字列出来，方便外部调用。
"""
from .retriever import get_retriever, get_retrievers			# 正经注释：检索器工厂函数 / 大白话注释：创建搜索引擎的函数
from .query_processing import plan_research_outline, get_search_results	# 正经注释：查询处理函数 / 大白话注释：拆问题 + 搜资料的函数
from .agent_creator import extract_json_with_regex, choose_agent	# 正经注释：代理创建函数 / 大白话注释：选研究员 + 解析 JSON 的函数
from .web_scraping import scrape_urls							# 正经注释：网页抓取函数 / 大白话注释：爬网页的函数
from .report_generation import write_conclusion, summarize_url, generate_draft_section_titles, generate_report, write_report_introduction	# 正经注释：报告生成相关函数 / 大白话注释：写报告的各个函数
from .markdown_processing import extract_headers, extract_sections, table_of_contents, add_references	# 正经注释：Markdown 处理函数 / 大白话注释：处理报告格式的函数
from .utils import stream_output									# 正经注释：WebSocket 输出流函数 / 大白话注释：给前端发消息的函数

__all__ = [														# 正经注释：模块公开接口列表 / 大白话注释：对外提供的所有函数名
    "get_retriever",											# 正经注释：按名称获取检索器类 / 大白话注释：按名字找搜索引擎
    "get_retrievers",											# 正经注释：获取所有配置的检索器类列表 / 大白话注释：拿到所有搜索引擎
    "get_search_results",										# 正经注释：执行搜索 / 大白话注释：搜一下
    "plan_research_outline",									# 正经注释：规划研究大纲 / 大白话注释：制定调研计划
    "extract_json_with_regex",									# 正经注释：正则提取 JSON / 大白话注释：从文字里抠 JSON
    "scrape_urls",												# 正经注释：批量抓取 URL / 大白话注释：爬网页
    "write_conclusion",											# 正经注释：写结论 / 大白话注释：写总结
    "summarize_url",											# 正经注释：摘要 URL 内容 / 大白话注释：总结一个网页
    "generate_draft_section_titles",							# 正经注释：生成草稿章节标题 / 大白话注释：列小节标题
    "generate_report",											# 正经注释：生成完整报告 / 大白话注释：写报告
    "write_report_introduction",								# 正经注释：写报告引言 / 大白话注释：写开头
    "extract_headers",											# 正经注释：提取 Markdown 标题 / 大白话注释：挑出标题
    "extract_sections",											# 正经注释：提取 Markdown 章节 / 大白话注释：切成一段段
    "table_of_contents",										# 正经注释：生成目录 / 大白话注释：生成目录
    "add_references",											# 正经注释：添加参考文献 / 大白话注释：加参考资料
    "stream_output",											# 正经注释：流式输出 / 大白话注释：实时推送消息
    "choose_agent"												# 正经注释：选择研究代理 / 大白话注释：选研究员
]