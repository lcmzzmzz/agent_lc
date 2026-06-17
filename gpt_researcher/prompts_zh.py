import warnings
from datetime import date, datetime, timezone

from langchain_core.documents import Document

from .config import Config
from .utils.enum import ReportSource, ReportType, Tone
from .utils.enum import PromptFamily as PromptFamilyEnum
from typing import Callable, List, Dict, Any


## Prompt Families #############################################################

class PromptFamily:
    """通用 Prompt 格式化类（中文版）。

    方法分两类：
    1. Prompt 生成器：与 ReportType 枚举对应，通过 get_prompt_by_report_type 调用
    2. Prompt 方法：不固定签名，在 agent 代码中直接调用

    子类可以覆盖任意方法，但必须保持相同的方法名。
    """

    def __init__(self, config: Config):
        """初始化时保存配置实例，子类可以根据配置选择不同的提示词策略。"""
        self.cfg = config

    # MCP-specific prompts
    @staticmethod
    def generate_mcp_tool_selection_prompt(query: str, tools_info: List[Dict], max_tools: int = 3) -> str:
        """
        Generate prompt for LLM-based MCP tool selection.

        Args:
            query: The research query
            tools_info: List of available tools with their metadata
            max_tools: Maximum number of tools to select

        Returns:
            str: The tool selection prompt
        """
        import json

        return f"""你是一位研究助手，负责为研究任务选择最合适的工具。

研究查询："{query}"

可用工具列表：
{json.dumps(tools_info, indent=2)}

任务：分析所有工具，从中精确选出 {max_tools} 个与研究查询最相关的工具。

选择标准：
- 选择能提供与查询相关的信息、数据或见解的工具
- 优先选择能搜索、获取或访问相关内容的工具
- 考虑工具之间的互补性（例如不同数据来源的搭配）
- 排除与研究主题明显无关的工具

请返回以下格式的 JSON：
{{
  "selected_tools": [
    {{
      "index": 0,
      "name": "工具名称",
      "relevance_score": 9,
      "reason": "详细说明选择此工具的理由"
    }}
  ],
  "selection_reasoning": "整体选择策略的说明"
}}

根据与研究查询的相关性从高到低排列，选择恰好 {max_tools} 个工具。
"""

    @staticmethod
    def generate_mcp_research_prompt(query: str, selected_tools: List) -> str:
        """
        Generate prompt for MCP research execution with selected tools.

        Args:
            query: The research query
            selected_tools: List of selected MCP tools

        Returns:
            str: The research execution prompt
        """
        # Handle cases where selected_tools might be strings or objects with .name attribute
        tool_names = []
        for tool in selected_tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            else:
                tool_names.append(str(tool))

        return f"""你是一位拥有专用工具访问权限的研究助手。请对以下查询进行深入研究，并提供全面、准确的信息。

研究查询："{query}"

研究指令：
1. 使用可用工具收集与研究查询相关的信息
2. 如需全面覆盖，可多次调用不同工具
3. 如果某个工具调用失败或返回空结果，请尝试其他替代方法
4. 尽可能综合多个信息源的数据
5. 专注于与研究查询直接相关的客观事实信息

可用工具：{tool_names}

请进行深入研究并提供你的发现。策略性地使用工具来收集最相关、最全面的信息。"""

    # Image generation prompts
    @staticmethod
    def generate_image_analysis_prompt(
        query: str,
        sections: List[Dict[str, Any]],
        max_images: int = 3,
    ) -> str:
        """Generate prompt for analyzing which report sections need images.

        Args:
            query: The research query.
            sections: List of report sections with header and content.
            max_images: Maximum number of images to suggest.

        Returns:
            str: The analysis prompt.
        """
        sections_text = "\n\n".join([
            f"### 第 {i+1} 节：{s['header']}\n{s['content'][:500]}..."
            for i, s in enumerate(sections)
        ])

        return f"""分析以下研究报告的各章节，找出最能从配图或图表中获益的 {max_images} 个章节。

研究主题：{query}

报告章节：
{sections_text}

对每个推荐的章节，请提供：
1. 章节编号（从 1 开始）
2. 一个具体的、详细的图片生成提示词
3. 简要说明为什么该章节适合配图

重要指南：
- 选择视觉辅助能真正帮助理解的章节
- 关注概念说明、流程展示、数据对比、信息流或统计图表等天然适合可视化的内容
- 避免纯文字分析、引言或结论等章节
- 图片提示词应足够具体，以生成专业的相关插图
- 图片应具信息性和教育性，而非纯装饰
- 考虑示意图、流程图、对比图或概念插画等形式

请返回 JSON 格式：
{{
    "suggestions": [
        {{
            "section_number": 1,
            "section_header": "章节标题",
            "image_prompt": "生成插图的详细提示词...",
            "image_type": "diagram|flowchart|comparison|concept|data_visualization",
            "reason": "该章节适合配图的原因"
        }}
    ]
}}

只返回 JSON，不要附加其他文字。"""

    @staticmethod
    def generate_image_prompt_enhancement(
        base_prompt: str,
        section_content: str,
        research_topic: str,
    ) -> str:
        """Enhance an image prompt with context for better generation.

        Args:
            base_prompt: The base image generation prompt.
            section_content: Content from the report section.
            research_topic: The main research topic.

        Returns:
            str: Enhanced image prompt.
        """
        return f"""为以下研究报告创建一张专业、信息丰富的插图。

研究主题：{research_topic}

图片说明：{base_prompt}

报告上下文：
{section_content[:800]}

风格要求：
- 适合学术/商业报告的专业简洁设计
- 清晰易懂的视觉元素
- 现代极简美学风格
- 使用专业配色（蓝、青、灰为主）
- 图片中避免过多文字
- 高对比度，确保可读性
- 如展示数据或对比，需使用清晰的标签和图例
- 同时适配电子阅读和打印"""

    @staticmethod
    def generate_search_queries_prompt(
        question: str,
        parent_query: str,
        report_type: str,
        max_iterations: int = 3,
        context: List[Dict[str, Any]] = [],
    ):
        """Generates the search queries prompt for the given question.
        Args:
            question (str): The question to generate the search queries prompt for
            parent_query (str): The main question (only relevant for detailed reports)
            report_type (str): The report type
            max_iterations (int): The maximum number of search queries to generate
            context (str): Context for better understanding of the task with realtime web information

        Returns: str: The search queries prompt for the given question
        """

        if (
            report_type == ReportType.DetailedReport.value
            or report_type == ReportType.SubtopicReport.value
        ):
            task = f"{parent_query} - {question}"
        else:
            task = question

        context_prompt = f"""
你是一位资深研究助手，需要为以下任务生成搜索查询："{task}"。
上下文：{context}

请利用这些上下文来优化你的搜索查询。上下文提供了实时网络信息，可以帮助你生成更具体、更相关的查询。请考虑上下文中提到的当前事件、最新进展或特定细节。
""" if context else ""

        dynamic_example = ", ".join([f'"查询 {i+1}"' for i in range(max_iterations)])

        return f"""请为以下任务编写 {max_iterations} 个 Google 搜索查询，以便从网络上获取信息并形成客观观点："{task}"

假设当前日期为 {datetime.now(timezone.utc).strftime('%Y 年 %m 月 %d 日')}（如果需要）。

{context_prompt}
你必须以列表形式返回查询字符串，格式如下：[{dynamic_example}]。
回复中只能包含这个列表。
"""

    @staticmethod
    def generate_report_prompt(
        question: str,
        context,
        report_source: str,
        report_format="apa",
        total_words=1000,
        tone=None,
        language="chinese",
    ):
        """Generates the report prompt for the given question and research summary.
        Args: question (str): The question to generate the report prompt for
                research_summary (str): The research summary to generate the report prompt for
        Returns: str: The report prompt for the given question and research summary
        """

        reference_prompt = ""
        if report_source == ReportSource.Web.value:
            reference_prompt = f"""
你必须在报告末尾列出所有使用的来源 URL 作为参考文献，确保不重复引用同一来源，每个来源只引用一次。
每个 URL 应使用超链接格式：[网站名称](url)
此外，报告中引用相关内容时，必须在相应位置使用超链接引用来源 URL：

例如：作者姓名. (年份, 月份 日期). 网页标题. 网站名称. [网站名称](url)
"""
        else:
            reference_prompt = f"""
你必须在报告末尾列出所有使用的源文档名称作为参考文献，确保不重复引用同一来源，每个来源只引用一次。
"""

        tone_prompt = f"请使用{tone.value}的语气撰写报告。" if tone else ""

        return f"""
参考资料："{context}"
---
请使用以上资料，对以下问题或任务给出详细的报告回答："{question}"
报告应聚焦于回答该问题，结构清晰、内容充实、深入全面，尽可能包含事实和数据，至少 {total_words} 字。
你应该尽可能写长，充分利用所有相关和必要的信息。

请遵循以下所有指南：
- 你必须基于给定信息形成自己明确而有效的观点。不要给出笼统、空洞的结论。
- 你必须使用 Markdown 语法和 {report_format} 格式编写报告。
- 使用清晰的 Markdown 标题组织报告：# 表示主标题，## 表示主要章节，### 表示子章节。
- 展示结构化数据或对比内容时，使用 Markdown 表格增强可读性。
- 你必须优先使用相关性强、可靠性高、重要性高的来源。选择可信来源而非可靠性较低的来源。
- 在来源可信的前提下，优先引用较新的文章。
- 不要包含目录，但必须使用正确的 Markdown 标题（# ## ###）来清晰组织报告结构。
- 使用 {report_format} 格式的文内引用，在引用相关来源的句子或段落后使用 Markdown 超链接格式：([文内引用](url))
- 不要忘记在报告末尾按 {report_format} 格式添加参考文献列表，并附上完整 URL 链接（非超链接形式）。
- {reference_prompt}
- {tone_prompt}
你必须使用以下语言撰写报告：{language}。
请全力以赴，这对我非常重要。
假设当前日期为 {date.today()}。
"""

    @staticmethod
    def curate_sources(query, sources, max_results=10):
        return f"""你的目标是针对研究任务 "{query}" 评估和筛选所抓取的内容，
优先纳入相关且高质量的信息，尤其是包含统计数据、数字或具体数据的内容。

筛选后的最终列表将用作生成研究报告的上下文，因此请优先：
- 保留尽可能多的原始信息，尤其重视包含量化数据或独特见解的内容
- 纳入广泛的观点和洞见
- 仅过滤掉明显无关或完全不可用的内容

评估指南：
1. 评估每个来源时考虑以下因素：
   - 相关性：纳入与研究查询直接或部分相关的来源。倾向保留而非排除。
   - 可信度：优先使用权威来源，但除非来源明显不可靠，否则予以保留。
   - 时效性：优先使用最近的信息，除非旧数据仍有重要价值。
   - 客观性：即使有偏见也可以保留，只要提供了独特或互补的视角。
   - 量化价值：优先考虑包含统计数字、数据或其他具体事实的来源。
2. 来源选择：
   - 尽可能多地纳入相关来源，最多 {max_results} 个，注重广泛覆盖和多样性。
   - 优先选择包含统计数据、数字或可验证事实的来源。
   - 内容重叠可以接受，只要增加了深度，尤其涉及数据时。
   - 仅排除完全无关、严重过时或因内容质量差而不可用的来源。
3. 内容保留：
   - 不要改写、总结或压缩任何来源内容。
   - 保留所有可用信息，仅清理明显的垃圾内容或格式问题。
   - 保留含有价值数据或见解的边缘相关或片段内容。

待评估的来源列表：
{sources}

你必须以原始来源 JSON 列表格式返回回复。
回复中不能包含 markdown 格式或额外文字（如 ```json），只能返回 JSON 列表！
"""

    @staticmethod
    def generate_resource_report_prompt(
        question, context, report_source: str, report_format="apa", tone=None, total_words=1000, language="chinese"
    ):
        """Generates the resource report prompt for the given question and research summary.

        Args:
            question (str): The question to generate the resource report prompt for.
            context (str): The research summary to generate the resource report prompt for.

        Returns:
            str: The resource report prompt for the given question and research summary.
        """

        reference_prompt = ""
        if report_source == ReportSource.Web.value:
            reference_prompt = f"""
            你必须包含所有相关来源 URL。
            每个 URL 应使用超链接格式：[网站名称](url)
            """
        else:
            reference_prompt = f"""
            你必须在报告末尾列出所有使用的源文档名称作为参考文献，确保不重复引用同一来源，每个来源只引用一次。
        """

        return (
            f'"""{context}"""\n\n基于上述信息，为以下问题或主题生成一份参考资源推荐报告：'
            f' "{question}"。报告应详细分析每个推荐资源，'
            "解释每个来源如何帮助找到研究问题的答案。\n"
            "重点说明每个来源的相关性、可靠性和重要性。\n"
            "确保报告结构良好、内容详实、深入，并使用 Markdown 语法。\n"
            "适当使用 Markdown 表格和其他格式化功能来清晰组织和展示信息。\n"
            "尽可能包含相关的事实、数字和引用。\n"
            f"报告至少 {total_words} 字。\n"
            f"你必须使用以下语言撰写报告：{language}。\n"
            "你必须包含所有相关来源 URL。"
            "每个 URL 应使用超链接格式：[网站名称](url)"
            f"{reference_prompt}"
        )

    @staticmethod
    def generate_custom_report_prompt(
        query_prompt, context, report_source: str, report_format="apa", tone=None, total_words=1000, language: str = "chinese"
    ):
        return f'"{context}"\n\n{query_prompt}'

    @staticmethod
    def generate_outline_report_prompt(
        question, context, report_source: str, report_format="apa", tone=None,  total_words=1000, language: str = "chinese"
    ):
        """Generates the outline report prompt for the given question and research summary.
        Args: question (str): The question to generate the outline report prompt for
                research_summary (str): The research summary to generate the outline report prompt for
        Returns: str: The outline report prompt for the given question and research summary
        """

        return (
            f'"""{context}""" 使用上述信息，为以下问题或主题生成一份 Markdown 格式的研究报告大纲：'
            f' "{question}"。大纲应提供一个结构良好的研究报告框架，'
            "包括主要章节、子章节和需要涵盖的关键要点。"
            f"研究报告应详细、信息丰富、深入，至少 {total_words} 字。"
            "使用适当的 Markdown 语法来格式化大纲，确保可读性。"
            "考虑在适当位置使用 Markdown 表格和其他格式化功能来增强信息展示。"
        )

    @staticmethod
    def generate_deep_research_prompt(
        question: str,
        context: str,
        report_source: str,
        report_format="apa",
        tone=None,
        total_words=2000,
        language: str = "chinese"
    ):
        """Generates the deep research report prompt, specialized for handling hierarchical research results.
        Args:
            question (str): The research question
            context (str): The research context containing learnings with citations
            report_source (str): Source of the research (web, etc.)
            report_format (str): Report formatting style
            tone: The tone to use in writing
            total_words (int): Minimum word count
            language (str): Output language
        Returns:
            str: The deep research report prompt
        """
        reference_prompt = ""
        if report_source == ReportSource.Web.value:
            reference_prompt = f"""
你必须在报告末尾列出所有使用的来源 URL 作为参考文献，确保不重复引用同一来源，每个来源只引用一次。
每个 URL 应使用超链接格式：[网站名称](url)
此外，报告中引用相关内容时，必须在相应位置使用超链接引用来源 URL：

例如：作者姓名. (年份, 月份 日期). 网页标题. 网站名称. [网站名称](url)
"""
        else:
            reference_prompt = f"""
你必须在报告末尾列出所有使用的源文档名称作为参考文献，确保不重复引用同一来源，每个来源只引用一次。
"""

        tone_prompt = f"请使用{tone.value}的语气撰写报告。" if tone else ""

        return f"""
使用以下分层研究的资料和引用来源：

"{context}"

撰写一份全面的研究报告来回答以下问题："{question}"

报告要求：
1. 综合多个研究深度的信息
2. 融合来自不同研究分支的发现
3. 从基础知识到高级洞见，呈现连贯的叙事
4. 全文保持对来源的正确引用
5. 结构清晰，包含明确的章节和子章节
6. 至少 {total_words} 字
7. 遵循 {report_format} 格式和 Markdown 语法
8. 在展示对比数据、统计数据或结构化信息时，使用 Markdown 表格和其他格式化功能

额外要求：
- 优先呈现深层研究中涌现的洞见
- 突出不同研究分支之间的关联
- 包含相关的统计数据、数据和具体案例
- 你必须基于给定信息形成自己明确而有效的观点。不要给出笼统、空洞的结论。
- 你必须优先使用相关性强、可靠性高、重要性高的来源。选择可信来源而非可靠性较低的来源。
- 在来源可信的前提下，优先引用较新的文章。
- 使用 {report_format} 格式的文内引用，在引用相关来源的句子或段落后使用 Markdown 超链接格式：([文内引用](url))
- {tone_prompt}
- 使用 {language} 撰写报告

{reference_prompt}

请撰写一份详尽、扎实的研究报告，将所有收集到的信息综合成一个有机的整体。
假设当前日期为 {datetime.now(timezone.utc).strftime('%Y 年 %m 月 %d 日')}。
"""

    @staticmethod
    def auto_agent_instructions():
        return """
你的任务是根据用户提出的研究主题，自动判断该主题所属的专业领域，并为其分配合适的专家角色。无论问题复杂与否、是否有明确答案，都需要选择最匹配的专家来执行研究。

每个专家由以下两部分定义：
- server: 专家名称（包含一个 emoji 作为标识）
- agent_role_prompt: 该专家的角色描述和研究指令

你需要根据主题的领域来选择合适的专家名称和角色描述。

示例：
task: "苹果股票现在值得投资吗？"
response:
{
    "server": "💰 金融分析师",
    "agent_role_prompt": "你是一位经验丰富的金融分析师。你的目标是根据提供的数据和市场趋势，撰写全面、敏锐、客观、条理清晰的金融分析报告。"
}
task: "倒卖球鞋能赚钱吗？"
response:
{
    "server": "📈 商业分析师",
    "agent_role_prompt": "你是一位资深的商业分析专家。你的目标是根据商业数据、市场趋势和战略分析，撰写全面、有洞察力、客观、结构清晰的商业研究报告。"
}
task: "特拉维夫有哪些值得去的景点？"
response:
{
    "server": "🌍 旅行导游",
    "agent_role_prompt": "你是一位走遍全球的旅行导游专家。你的目标是为指定地点撰写生动有趣、内容详实、客观公正、结构清晰的旅行报告，包括历史背景、景点介绍和文化特色。"
}
task: "Python 异步编程如何入门？"
response:
{
    "server": "💻 软件工程师",
    "agent_role_prompt": "你是一位资深的软件工程师。你的目标是根据提供的技术资料和最佳实践，撰写准确、深入、客观、条理清晰的技术研究报告，包含概念解析、代码示例和实践建议。"
}
task: "感冒了吃什么药好得快？"
response:
{
    "server": "🏥 医学顾问",
    "agent_role_prompt": "你是一位专业的医学顾问。你的目标是根据循证医学资料，撰写准确、客观、审慎、结构清晰的健康报告，包含病因分析、治疗方案和注意事项，并在必要时注明信息来源的局限性。"
}
"""

    @staticmethod
    def generate_summary_prompt(query, data):
        """Generates the summary prompt for the given question and text.
        Args: question (str): The question to generate the summary prompt for
                text (str): The text to generate the summary prompt for
        Returns: str: The summary prompt for the given question and text
        """

        return (
            f'{data}\n 请使用以上文本，根据以下任务或查询进行摘要："{query}"。\n 如果 '
            f"无法用该文本回答问题，你必须对文本进行简短摘要。\n 尽可能包含所有事实信息，"
            f"如数字、统计数据、引用等。"
        )

    @staticmethod
    def generate_quick_summary_prompt(query: str, context: str) -> str:
        """Generates the quick summary prompt for the given question and context.
        Args:
            query (str): The query to generate the summary for
            context (str): The search results to summarize
        Returns:
            str: The quick summary prompt
        """
        return f"""
仅根据提供的搜索结果，为以下查询合成一个全面的回答。
查询："{query}"

搜索结果：
{context}

指令：
1. 提供一个单一的、连贯的叙述性摘要。
2. 使用数字 [1]、[2] 等引用来源，与搜索结果编号对应。
3. 如果搜索结果不足以回答查询，请明确说明。
4. 专注于准确性和相关性。
"""

    @staticmethod
    def pretty_print_docs(docs: list[Document], top_n: int | None = None) -> str:
        """Compress the list of documents into a context string"""
        return f"\n".join(f"来源：{d.metadata.get('source')}\n"
                          f"标题：{d.metadata.get('title')}\n"
                          f"内容：{d.page_content}\n"
                          for i, d in enumerate(docs)
                          if top_n is None or i < top_n)

    @staticmethod
    def join_local_web_documents(docs_context: str, web_context: str) -> str:
        """Joins local web documents with context scraped from the internet"""
        return f"来自本地文档的上下文：{docs_context}\n\n来自网络来源的上下文：{web_context}"

    ################################################################################################

    # DETAILED REPORT PROMPTS

    @staticmethod
    def generate_subtopics_prompt() -> str:
        return """
给定主主题：

{task}

和研究资料：

{data}

- 构建一个子主题列表，标明将在最终报告中生成的各章节标题。
- 可能的子主题列表：{subtopics}。
- 不得有重复的子主题。
- 子主题数量最多不超过 {max_subtopics} 个。
- 最后按相关性和有意义的顺序排列子主题，使其适合详细报告的结构呈现。

"重要!"：
- 每个子主题必须且仅与主主题及提供的研究资料相关！

{format_instructions}
"""

    @staticmethod
    def generate_subtopic_report_prompt(
        current_subtopic,
        existing_headers: list,
        relevant_written_contents: list,
        main_topic: str,
        context,
        report_format: str = "apa",
        max_subsections=5,
        total_words=800,
        tone: Tone = Tone.Objective,
        language: str = "chinese",
    ) -> str:
        return f"""
上下文：
"{context}"

主主题与子主题：
使用最新的可用信息，为子主题 "{current_subtopic}"（主主题为 "{main_topic}"）撰写一份详细报告。
最多 {max_subsections} 个子章节。

内容重点：
- 报告应聚焦于回答问题，结构清晰、信息丰富、深入细致，尽可能包含事实和数字。
- 使用 Markdown 语法，遵循 {report_format.upper()} 格式。
- 在展示数据、对比或结构化信息时，使用 Markdown 表格增强可读性。

重要：内容与章节的独特性：
- 这部分指令至关重要，确保内容独一无二且不与已有报告重叠。
- 在撰写任何新子章节之前，务必仔细检查下方提供的已有标题和已有撰写内容。
- 避免任何已在已有撰写内容中涵盖的信息。
- 不要将已有标题用作新子章节的标题。
- 不要重复已有撰写内容中已涵盖的信息或高度相似的变体，以避免重复。
- 确保有嵌套子章节时同样不重叠。
- 确保你的内容完全是新的，不与之前子主题报告中的任何信息重叠。

"已有子主题报告"：
- 已有子主题报告及其章节标题：

    {existing_headers}

- 已有子主题报告中已撰写的内容：

    {relevant_written_contents}

"结构与格式"：
- 由于本子报告将是一个更大报告的一部分，只包含正文，不需要引言或结论部分。

- 你必须在引用相关来源 URL 的正文位置使用 Markdown 超链接，例如：

    ### 章节标题

    这是一段示例文字 ([文内引用](url))。

- 主标题使用 H2 (##)，子章节使用 H3 (###)。
- 使用较小的 Markdown 标题（如 H2 或 H3）来组织内容，避免使用最大标题（H1），因为 H1 将用于整个报告的标题。
- 将内容组织成不同的章节，补充但不与已有报告重叠。
- 如果添加与已有报告相似或相同的子章节，需要明确指出新内容与已有内容的区别。例如：

    ### 新标题（与已有标题相似的主题）

    前一节讨论了[主题 A]，本节将探讨[主题 B]。"

"日期"：
假设当前日期为 {datetime.now(timezone.utc).strftime('%Y 年 %m 月 %d 日')}（如果需要）。

"重要!"：
- 你必须使用以下语言撰写报告：{language}。
- 重点必须放在主主题上！必须排除任何与主主题无关的信息！
- 不得包含引言、结论、摘要或参考文献部分。
- 你必须使用 {report_format.upper()} 格式的文内引用，在引用相关来源的句子或段落后使用 Markdown 超链接格式：([文内引用](url))。
- 如果添加了相似或相同的子章节，必须在报告中说明已有内容与新内容的区别。
- 报告至少 {total_words} 字。
- 全文使用 {tone.value} 的语气。

不要添加结论部分。
"""

    @staticmethod
    def generate_draft_titles_prompt(
        current_subtopic: str,
        main_topic: str,
        context: str,
        max_subsections: int = 5
    ) -> str:
        return f"""
"上下文"：
"{context}"

"主主题与子主题"：
使用最新的可用信息，为子主题 "{current_subtopic}"（主主题为 "{main_topic}"）的详细报告草拟章节标题。

"任务"：
1. 为子主题报告创建一个草拟章节标题列表。
2. 每个标题应简明扼要且与子主题相关。
3. 标题不应太过于笼统，而应足够详细，以涵盖子主题的主要方面。
4. 使用 Markdown 语法，H3 (###)，因为 H1 和 H2 将用于更大报告的标题。
5. 确保标题涵盖子主题的主要方面。

"结构与格式"：
请使用 Markdown 语法以列表形式提供草拟标题，例如：

### 标题 1
### 标题 2
### 标题 3

"重要!"：
- 重点必须放在主主题上！必须排除任何与主主题无关的信息！
- 不得包含引言、结论、摘要或参考文献部分。
- 只创建标题，不创建内容。
"""

    @staticmethod
    def generate_report_introduction(question: str, research_summary: str = "", language: str = "chinese", report_format: str = "apa") -> str:
        return f"""{research_summary}\n
使用上述最新信息，为以下主题撰写详细的报告引言 -- {question}。
- 引言应简洁、结构清晰、信息丰富，使用 Markdown 语法。
- 由于此引言将是一个更大报告的一部分，不要包含报告中通常出现的其他部分。
- 引言前应使用 H1 标题，给出整个报告的合适主题标题。
- 你必须使用 {report_format.upper()} 格式的文内引用，在引用相关来源的句子或段落后使用 Markdown 超链接格式：([文内引用](url))。
假设当前日期为 {datetime.now(timezone.utc).strftime('%Y 年 %m 月 %d 日')}（如果需要）。
- 输出必须使用 {language} 语言。
"""


    @staticmethod
    def generate_report_conclusion(query: str, report_content: str, language: str = "chinese", report_format: str = "apa") -> str:
        """
        Generate a concise conclusion summarizing the main findings and implications of a research report.

        Args:
            query (str): The research task or question.
            report_content (str): The content of the research report.
            language (str): The language in which the conclusion should be written.

        Returns:
            str: A concise conclusion summarizing the report's main findings and implications.
        """
        prompt = f"""
根据以下研究报告和研究任务，请撰写一段简洁的结论，总结主要发现及其影响：

研究任务：{query}

研究报告：{report_content}

你的结论应：
1. 概括研究的主要观点
2. 突出最重要的发现
3. 讨论其影响或后续方向
4. 大约 2-3 段

如果报告末尾还没有 "## 结论" 章节标题，请在结论顶部添加。
你必须使用 {report_format.upper()} 格式的文内引用，在引用相关来源的句子或段落后使用 Markdown 超链接格式：([文内引用](url))。

重要：整段结论必须使用 {language} 语言撰写。

撰写结论：
"""

        return prompt


## Factory ######################################################################

# This is the function signature for the various prompt generator functions
PROMPT_GENERATOR = Callable[
    [
        str,        # question
        str,        # context
        str,        # report_source
        str,        # report_format
        str | None, # tone
        int,        # total_words
        str,        # language
    ],
    str,
]

report_type_mapping = {
    ReportType.ResearchReport.value: "generate_report_prompt",
    ReportType.ResourceReport.value: "generate_resource_report_prompt",
    ReportType.OutlineReport.value: "generate_outline_report_prompt",
    ReportType.CustomReport.value: "generate_custom_report_prompt",
    ReportType.SubtopicReport.value: "generate_subtopic_report_prompt",
    ReportType.DeepResearch.value: "generate_deep_research_prompt",
}


def get_prompt_by_report_type(
    report_type: str,
    prompt_family: type[PromptFamily] | PromptFamily,
):
    prompt_by_type = getattr(prompt_family, report_type_mapping.get(report_type, ""), None)
    default_report_type = ReportType.ResearchReport.value
    if not prompt_by_type:
        warnings.warn(
            f"无效的报告类型：{report_type}。\n"
            f"请使用以下类型之一：{', '.join([enum_value for enum_value in report_type_mapping.keys()])}\n"
            f"使用默认报告类型：{default_report_type}。",
            UserWarning,
        )
        prompt_by_type = getattr(prompt_family, report_type_mapping.get(default_report_type))
    return prompt_by_type


def get_prompt_family(
    prompt_family_name: PromptFamilyEnum | str, config: Config,
) -> PromptFamily:
    """Get a prompt family by name or value."""
    if isinstance(prompt_family_name, PromptFamilyEnum):
        prompt_family_name = prompt_family_name.value
    if prompt_family_name == PromptFamilyEnum.Default.value:
        return PromptFamily(config)
    warnings.warn(
        f"中文版不支持当前指定的 prompt family：{prompt_family_name}。\n"
        f"已使用默认中文 PromptFamily。",
        UserWarning,
    )
    return PromptFamily()