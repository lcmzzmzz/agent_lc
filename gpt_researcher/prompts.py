"""
【正经注释】
提示模板模块，定义了 GPT Researcher 所有 LLM 交互的提示词模板。
通过 PromptFamily 体系支持不同模型的差异化提示策略，涵盖搜索查询生成、
报告撰写、摘要生成、子主题拆分、MCP 工具选择、图像分析等全部提示场景。

【大白话注释】
这个文件就是整个系统的"话术库"——所有发给 AI 的提示词模板都住在这里。
不同的报告类型有不同的模板，不同的 AI 模型（比如 IBM Granite）也有自己的专属模板。
说白了就是教 AI 怎么干活的各种"指令说明书"。
"""

import warnings  # 正经注释：标准库，用于发出用户警告（如无效的报告类型或提示族） / 大白话注释：用来给用户弹警告的，比如你传了个不认识的报告类型
from datetime import date, datetime, timezone  # 正经注释：日期时间处理，用于在提示词中注入当前日期 / 大白话注释：告诉 AI "今天是几号"，这样它写报告时日期不会搞错

from langchain_core.documents import Document  # 正经注释：LangChain 核心文档类型，用于文档数据的标准化传递 / 大白话注释：LangChain 的文档格式，拿来装网页内容的

from .config import Config  # 正经注释：项目配置类，提供模型名称、提供商等运行时参数 / 大白话注释：配置大管家，知道该用哪个 AI 模型
from .utils.enum import ReportSource, ReportType, Tone  # 正经注释：报告源类型、报告类型、语气风格的枚举定义 / 大白话注释：一堆常量选项——报告从哪来、什么格式、什么调调
from .utils.enum import PromptFamily as PromptFamilyEnum  # 正经注释：提示族枚举，用于标识使用哪套提示模板 / 大白话注释：提示词"门派"的选项，不同 AI 模型用不同门派的模板
from typing import Callable, List, Dict, Any  # 正经注释：类型注解工具，用于函数签名的静态类型提示 / 大白话注释：告诉代码阅读者"这个变量是什么类型的"


## Prompt Families #############################################################
# 正经注释：提示族区域分隔标记，以下是各种提示模板族的定义 / 大白话注释：下面就是各种"话术门派"的地盘

class PromptFamily:
    """General purpose class for prompt formatting.

    This may be overwritten with a derived class that is model specific. The
    methods are broken down into two groups:

    1. Prompt Generators: These follow a standard format and are correlated with
        the ReportType enum. They should be accessed via
        get_prompt_by_report_type

    2. Prompt Methods: These are situation-specific methods that do not have a
        standard signature and are accessed directly in the agent code.

    All derived classes must retain the same set of method names, but may
    override individual methods.

    【正经注释】
    通用提示格式化基类，定义所有提示模板的标准接口。
    方法分为两组：(1) 提示生成器，与 ReportType 枚举一一对应，通过工厂函数访问；
    (2) 提示方法，特定场景使用，在 agent 代码中直接调用。
    派生类（如 Granite 系列）必须保持相同的方法名集合，但可以覆盖个别方法实现。

    【大白话注释】
    这是"话术大全"的基础版，所有提示词模板的老祖宗。
    它提供了一套标准的方法名，子类可以"魔改"某些方法来适配不同的 AI 模型。
    简单说就是：默认的话术都在这里，不同的 AI 模型可以继承它然后改掉自己不爽的部分。
    """

    def __init__(self, config: Config):
        """Initialize with a config instance. This may be used by derived
        classes to select the correct prompting based on configured models and/
        or providers

        【正经注释】
        使用配置实例初始化提示族。派生类可据此根据模型和提供商选择合适的提示策略。

        【大白话注释】
        把配置对象存起来，后面生成提示词时可能要用到配置里的模型名、提供商等信息。
        """
        self.cfg = config  # 正经注释：保存配置实例引用，供后续方法访问模型参数 / 大白话注释：把配置本子揣兜里，随时翻看

    # MCP-specific prompts
    # 正经注释：MCP（Model Context Protocol）相关的提示词，用于工具选择和研究执行 / 大白话注释：MCP 就是让 AI 能调用外部工具的协议，下面是跟工具相关的提示词

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

        【正经注释】
        生成用于让 LLM 从可用 MCP 工具列表中选择最相关工具的提示词。
        LLM 会根据研究查询的语义，分析工具的元数据，选出最合适的一组工具。

        【大白话注释】
        给 AI 一堆工具的说明书，让它挑出最适合当前研究任务的几个工具。
        就像你去五金店，告诉老板你要修水管，老板帮你挑合适的扳手和胶带。
        """
        import json  # 正经注释：延迟导入 json 模块，用于将工具信息序列化为 JSON 格式嵌入提示词 / 大白话注释：把工具信息变成 JSON 字符串塞进提示词里
        
        return f"""You are a research assistant helping to select the most relevant tools for a research query.

RESEARCH QUERY: "{query}"

AVAILABLE TOOLS:
{json.dumps(tools_info, indent=2)}

TASK: Analyze the tools and select EXACTLY {max_tools} tools that are most relevant for researching the given query.

SELECTION CRITERIA:
- Choose tools that can provide information, data, or insights related to the query
- Prioritize tools that can search, retrieve, or access relevant content
- Consider tools that complement each other (e.g., different data sources)
- Exclude tools that are clearly unrelated to the research topic

Return a JSON object with this exact format:
{{
  "selected_tools": [
    {{
      "index": 0,
      "name": "tool_name",
      "relevance_score": 9,
      "reason": "Detailed explanation of why this tool is relevant"
    }}
  ],
  "selection_reasoning": "Overall explanation of the selection strategy"
}}

Select exactly {max_tools} tools, ranked by relevance to the research query.
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

        【正经注释】
        生成 MCP 研究执行提示词，指导 LLM 使用已选定的工具进行研究。
        该提示词要求 LLM 综合利用多个工具、处理失败情况并聚焦事实信息。

        【大白话注释】
        告诉 AI："这几个工具我已经给你选好了，你用它们来查资料吧。"
        同时提醒它：工具挂了别慌，换个方式继续搞。
        """
        # Handle cases where selected_tools might be strings or objects with .name attribute
        # 正经注释：兼容处理工具对象可能是字符串或具有 name 属性的对象两种情况 / 大白话注释：工具可能是对象也可能是字符串，统一提取名字
        tool_names = []
        for tool in selected_tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            else:
                tool_names.append(str(tool))
        
        return f"""You are a research assistant with access to specialized tools. Your task is to research the following query and provide comprehensive, accurate information.

RESEARCH QUERY: "{query}"

INSTRUCTIONS:
1. Use the available tools to gather relevant information about the query
2. Call multiple tools if needed to get comprehensive coverage
3. If a tool call fails or returns empty results, try alternative approaches
4. Synthesize information from multiple sources when possible
5. Focus on factual, relevant information that directly addresses the query

AVAILABLE TOOLS: {tool_names}

Please conduct thorough research and provide your findings. Use the tools strategically to gather the most relevant and comprehensive information."""

    # Image generation prompts
    # 正经注释：图像生成相关的提示词，用于分析报告哪些章节适合配图 / 大白话注释：跟"给报告配图"相关的提示词

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

        【正经注释】
        生成图像分析提示词，让 LLM 判断报告的哪些章节最适合添加可视化插图。
        返回 JSON 格式的建议列表，包含章节号、图像提示词和推荐理由。

        【大白话注释】
        把报告的各个章节喂给 AI，让它挑出最需要配图的几个章节。
        不是随便配图，而是找那些"一图胜千言"的地方，比如数据对比、流程说明之类的。
        """
        sections_text = "\n\n".join([
            f"### Section {i+1}: {s['header']}\n{s['content'][:500]}..."
            for i, s in enumerate(sections)
        ])  # 正经注释：将章节列表格式化为 Markdown 文本，每段内容截取前 500 字符 / 大白话注释：把章节拼成一段文字，每段只取前 500 字防止太长
        
        return f"""Analyze the following research report sections and identify which {max_images} sections would benefit MOST from a visual illustration or diagram.

RESEARCH TOPIC: {query}

REPORT SECTIONS:
{sections_text}

For each recommended section, provide:
1. The section number (1-indexed)
2. A specific, detailed image prompt that would create an informative illustration
3. A brief explanation of why this section benefits from visualization

IMPORTANT GUIDELINES:
- Choose sections where visual representation would genuinely aid understanding
- Focus on concepts, processes, comparisons, data flows, or statistics that are inherently visual
- Avoid sections that are purely textual analysis, introductions, or conclusions
- The image prompt should be specific enough to generate a relevant, professional illustration
- Images should be informative and educational, not decorative
- Consider diagrams, flowcharts, comparison charts, or conceptual illustrations

Respond in JSON format:
{{
    "suggestions": [
        {{
            "section_number": 1,
            "section_header": "Section Title",
            "image_prompt": "Detailed prompt for generating an informative illustration...",
            "image_type": "diagram|flowchart|comparison|concept|data_visualization",
            "reason": "Why this section benefits from visualization"
        }}
    ]
}}

Return ONLY the JSON, no additional text."""

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

        【正经注释】
        利用报告章节内容和研究主题上下文增强基础图像提示词，
        添加专业风格要求（配色、设计语言、对比度等），提高生成图像的质量和相关性。

        【大白话注释】
        原来的图片提示词太简单了，给它加点料——把报告内容、研究主题、
        风格要求都塞进去，让生成的图片更专业、更贴合报告内容。
        """
        return f"""Create a professional, informative illustration for a research report.

RESEARCH TOPIC: {research_topic}

IMAGE DESCRIPTION: {base_prompt}

CONTEXT FROM REPORT:
{section_content[:800]}

STYLE REQUIREMENTS:
- Professional and clean design suitable for academic/business reports
- Clear, easy-to-understand visual elements
- Modern, minimalist aesthetic
- Use a professional color palette (blues, teals, grays)
- Avoid excessive text in the image
- High contrast for readability
- If showing data or comparisons, use clear labels and legends
- Suitable for both digital viewing and printing"""

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

        【正经注释】
        根据研究问题生成搜索查询提示词。对于详细报告和子主题报告类型，
        会将父查询与子问题合并；同时支持注入实时网络上下文以优化查询质量。

        【大白话注释】
        让 AI 帮你想几个搜索关键词。如果是详细报告，会把大主题和小问题拼在一起；
        如果有实时搜索结果作为上下文，AI 还能根据最新消息来调整搜索策略。
        """

        if (
            report_type == ReportType.DetailedReport.value
            or report_type == ReportType.SubtopicReport.value
        ):
            task = f"{parent_query} - {question}"  # 正经注释：详细报告类型需合并父查询与子问题 / 大白话注释：大报告的子章节，要把大标题和小标题拼起来
        else:
            task = question

        context_prompt = f"""
You are a seasoned research assistant tasked with generating search queries to find relevant information for the following task: "{task}".
Context: {context}

Use this context to inform and refine your search queries. The context provides real-time web information that can help you generate more specific and relevant queries. Consider any current events, recent developments, or specific details mentioned in the context that could enhance the search queries.
""" if context else ""  # 正经注释：仅在存在上下文时才注入上下文提示段落 / 大白话注释：有背景信息就塞进去，没有就拉倒

        dynamic_example = ", ".join([f'"query {i+1}"' for i in range(max_iterations)])  # 正经注释：动态生成格式示例字符串，与查询数量对应 / 大白话注释：造几个假例子告诉 AI 输出长什么样

        return f"""Write {max_iterations} google search queries to search online that form an objective opinion from the following task: "{task}"

Assume the current date is {datetime.now(timezone.utc).strftime('%B %d, %Y')} if required.

{context_prompt}
You must respond with a list of strings in the following format: [{dynamic_example}].
The response should contain ONLY the list.
"""

    @staticmethod
    def generate_report_prompt(
        question: str,
        context,
        report_source: str,
        report_format="apa",
        total_words=1000,
        tone=None,
        language="english",
    ):
        """Generates the report prompt for the given question and research summary.
        Args: question (str): The question to generate the report prompt for
                research_summary (str): The research summary to generate the report prompt for
        Returns: str: The report prompt for the given question and research summary

        【正经注释】
        生成标准研究报告提示词。根据报告来源（Web/文档）生成不同的引用要求，
        支持自定义格式（APA等）、字数、语气和输出语言。

        【大白话注释】
        这是生成最终研究报告的核心提示词。告诉 AI：资料给你了，照着这个题目写报告，
        要用 APA 格式、至少多少字、什么语气、什么语言。网上的资料要附链接，本地文档要附文件名。
        """

        reference_prompt = ""
        if report_source == ReportSource.Web.value:  # 正经注释：根据报告来源类型选择不同的引用格式要求 / 大白话注释：资料是网上搜来的，就要加超链接引用
            reference_prompt = f"""
You MUST write all used source urls at the end of the report as references, and make sure to not add duplicated sources, but only one reference for each.
Every url should be hyperlinked: [url website](url)
Additionally, you MUST include hyperlinks to the relevant URLs wherever they are referenced in the report:

eg: Author, A. A. (Year, Month Date). Title of web page. Website Name. [url website](url)
"""
        else:  # 正经注释：非 Web 来源使用文档名称引用格式 / 大白话注释：资料是本地文档，就写文件名就行
            reference_prompt = f"""
You MUST write all used source document names at the end of the report as references, and make sure to not add duplicated sources, but only one reference for each."
"""

        tone_prompt = f"Write the report in a {tone.value} tone." if tone else ""  # 正经注释：仅在指定语气时才注入语气提示 / 大白话注释：指定了语气就加上，没指定就不管

        return f"""
Information: "{context}"
---
Using the above information, answer the following query or task: "{question}" in a detailed report --
The report should focus on the answer to the query, should be well structured, informative,
in-depth, and comprehensive, with facts and numbers if available and at least {total_words} words.
You should strive to write the report as long as you can using all relevant and necessary information provided.

Please follow all of the following guidelines in your report:
- You MUST determine your own concrete and valid opinion based on the given information. Do NOT defer to general and meaningless conclusions.
- You MUST write the report with markdown syntax and {report_format} format.
- Structure your report with clear markdown headers: use # for the main title, ## for major sections, and ### for subsections.
- Use markdown tables when presenting structured data or comparisons to enhance readability.
- You MUST prioritize the relevance, reliability, and significance of the sources you use. Choose trusted sources over less reliable ones.
- You must also prioritize new articles over older articles if the source can be trusted.
- You MUST NOT include a table of contents, but DO include proper markdown headers (# ## ###) to structure your report clearly.
- Use in-text citation references in {report_format} format and make it with markdown hyperlink placed at the end of the sentence or paragraph that references them like this: ([in-text citation](url)).
- Don't forget to add a reference list at the end of the report in {report_format} format and full url links without hyperlinks.
- {reference_prompt}
- {tone_prompt}
You MUST write the report in the following language: {language}.
Please do your best, this is very important to my career.
Assume that the current date is {date.today()}.
"""

    @staticmethod
    def curate_sources(query, sources, max_results=10):
        """
        【正经注释】
        生成来源筛选提示词，指导 LLM 从抓取的内容中评估和精选高质量信息源。
        优先保留含有统计数据和量化信息的来源，同时确保视角多样性。
        要求以原始 JSON 格式返回筛选结果，不重写不摘要。

        【大白话注释】
        从一堆搜来的资料里挑出好东西。有数据的优先留，没用的扔掉。
        告诉 AI：别改写内容，原样还给我，只帮我把垃圾过滤掉就行。

        Args:
            query: 研究查询
            sources: 待筛选的来源列表
            max_results: 最大保留数量
        Returns:
            str: 来源筛选提示词
        """
        return f"""Your goal is to evaluate and curate the provided scraped content for the research task: "{query}"
    while prioritizing the inclusion of relevant and high-quality information, especially sources containing statistics, numbers, or concrete data.

The final curated list will be used as context for creating a research report, so prioritize:
- Retaining as much original information as possible, with extra emphasis on sources featuring quantitative data or unique insights
- Including a wide range of perspectives and insights
- Filtering out only clearly irrelevant or unusable content

EVALUATION GUIDELINES:
1. Assess each source based on:
   - Relevance: Include sources directly or partially connected to the research query. Err on the side of inclusion.
   - Credibility: Favor authoritative sources but retain others unless clearly untrustworthy.
   - Currency: Prefer recent information unless older data is essential or valuable.
   - Objectivity: Retain sources with bias if they provide a unique or complementary perspective.
   - Quantitative Value: Give higher priority to sources with statistics, numbers, or other concrete data.
2. Source Selection:
   - Include as many relevant sources as possible, up to {max_results}, focusing on broad coverage and diversity.
   - Prioritize sources with statistics, numerical data, or verifiable facts.
   - Overlapping content is acceptable if it adds depth, especially when data is involved.
   - Exclude sources only if they are entirely irrelevant, severely outdated, or unusable due to poor content quality.
3. Content Retention:
   - DO NOT rewrite, summarize, or condense any source content.
   - Retain all usable information, cleaning up only clear garbage or formatting issues.
   - Keep marginally relevant or incomplete sources if they contain valuable data or insights.

SOURCES LIST TO EVALUATE:
{sources}

You MUST return your response in the EXACT sources JSON list format as the original sources.
The response MUST not contain any markdown format or additional text (like ```json), just the JSON list!
"""

    @staticmethod
    def generate_resource_report_prompt(
        question, context, report_source: str, report_format="apa", tone=None, total_words=1000, language="english"
    ):
        """Generates the resource report prompt for the given question and research summary.

        Args:
            question (str): The question to generate the resource report prompt for.
            context (str): The research summary to generate the resource report prompt for.

        Returns:
            str: The resource report prompt for the given question and research summary.

        【正经注释】
        生成资源报告提示词，产出的是参考文献推荐报告而非传统研究报告。
        侧重分析每个推荐资源的价值、相关性和可靠性，说明其对研究问题的贡献。

        【大白话注释】
        不是写普通报告，是写"参考资料推荐报告"——告诉你哪些资料值得看、为什么值得看。
        就像老师给你开书单，每个推荐都附带说明。
        """

        reference_prompt = ""
        if report_source == ReportSource.Web.value:  # 正经注释：Web 来源要求附带超链接 URL / 大白话注释：网上的资料要贴链接
            reference_prompt = f"""
            You MUST include all relevant source urls.
            Every url should be hyperlinked: [url website](url)
            """
        else:  # 正经注释：本地文档来源要求列出文档名称 / 大白话注释：本地的资料写文件名
            reference_prompt = f"""
            You MUST write all used source document names at the end of the report as references, and make sure to not add duplicated sources, but only one reference for each."
        """

        return (
            f'"""{context}"""\n\nBased on the above information, generate a bibliography recommendation report for the following'
            f' question or topic: "{question}". The report should provide a detailed analysis of each recommended resource,'
            " explaining how each source can contribute to finding answers to the research question.\n"
            "Focus on the relevance, reliability, and significance of each source.\n"
            "Ensure that the report is well-structured, informative, in-depth, and follows Markdown syntax.\n"
            "Use markdown tables and other formatting features when appropriate to organize and present information clearly.\n"
            "Include relevant facts, figures, and numbers whenever available.\n"
            f"The report should have a minimum length of {total_words} words.\n"
            f"You MUST write the report in the following language: {language}.\n"
            "You MUST include all relevant source urls."
            "Every url should be hyperlinked: [url website](url)"
            f"{reference_prompt}"
        )

    @staticmethod
    def generate_custom_report_prompt(
        query_prompt, context, report_source: str, report_format="apa", tone=None, total_words=1000, language: str = "english"
    ):
        """
        【正经注释】
        生成自定义报告提示词。直接将用户提供的自定义查询提示与上下文拼接，
        赋予用户完全的报告格式和内容控制权。

        【大白话注释】
        最自由的报告模板——你想怎么写就怎么写。
        把你自定义的提示词和搜到的资料拼在一起丢给 AI，剩下的你说了算。

        Args:
            query_prompt: 用户自定义的查询提示
            context: 研究上下文
        Returns:
            str: 自定义报告提示词
        """
        return f'"{context}"\n\n{query_prompt}'  # 正经注释：将上下文与自定义提示直接拼接 / 大白话注释：资料 + 你的指令，简单粗暴拼一起

    @staticmethod
    def generate_outline_report_prompt(
        question, context, report_source: str, report_format="apa", tone=None,  total_words=1000, language: str = "english"
    ):
        """Generates the outline report prompt for the given question and research summary.
        Args: question (str): The question to generate the outline report prompt for
                research_summary (str): The research summary to generate the outline report prompt for
        Returns: str: The outline report prompt for the given question and research summary

        【正经注释】
        生成大纲报告提示词。不生成完整报告正文，只生成结构化的报告大纲框架，
        包含主要章节、子章节和要点概述，使用 Markdown 语法格式化。

        【大白话注释】
        先别急着写报告，先列个大纲看看。
        告诉 AI：根据这些资料，帮我搭一个报告骨架，写清楚每章每节要讲啥。
        """

        return (
            f'"""{context}""" Using the above information, generate an outline for a research report in Markdown syntax'
            f' for the following question or topic: "{question}". The outline should provide a well-structured framework'
            " for the research report, including the main sections, subsections, and key points to be covered."
            f" The research report should be detailed, informative, in-depth, and a minimum of {total_words} words."
            " Use appropriate Markdown syntax to format the outline and ensure readability."
            " Consider using markdown tables and other formatting features where they would enhance the presentation of information."
        )

    @staticmethod
    def generate_deep_research_prompt(
        question: str,
        context: str,
        report_source: str,
        report_format="apa",
        tone=None,
        total_words=2000,
        language: str = "english"
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

        【正经注释】
        生成深度研究报告提示词，专门处理分层递进式研究的多层级结果。
        要求综合不同研究深度的发现，整合各研究分支的成果，从基础到高级构建连贯叙述。
        默认最低 2000 字，比标准报告更详尽。

        【大白话注释】
        这是给"深度研究模式"专用的终极报告提示词。
        因为深度研究是一层一层挖下去的（先搜一轮，再根据结果继续搜），所以提示词要求 AI
        把所有层级挖到的信息整合到一起，写一份又长又详细的终极报告。
        """
        reference_prompt = ""
        if report_source == ReportSource.Web.value:  # 正经注释：Web 来源要求附带超链接引用 / 大白话注释：网上资料要贴链接
            reference_prompt = f"""
You MUST write all used source urls at the end of the report as references, and make sure to not add duplicated sources, but only one reference for each.
Every url should be hyperlinked: [url website](url)
Additionally, you MUST include hyperlinks to the relevant URLs wherever they are referenced in the report:

eg: Author, A. A. (Year, Month Date). Title of web page. Website Name. [url website](url)
"""
        else:
            reference_prompt = f"""
You MUST write all used source document names at the end of the report as references, and make sure to not add duplicated sources, but only one reference for each."
"""

        tone_prompt = f"Write the report in a {tone.value} tone." if tone else ""

        return f"""
Using the following hierarchically researched information and citations:

"{context}"

Write a comprehensive research report answering the query: "{question}"

The report should:
1. Synthesize information from multiple levels of research depth
2. Integrate findings from various research branches
3. Present a coherent narrative that builds from foundational to advanced insights
4. Maintain proper citation of sources throughout
5. Be well-structured with clear sections and subsections
6. Have a minimum length of {total_words} words
7. Follow {report_format} format with markdown syntax
8. Use markdown tables, lists and other formatting features when presenting comparative data, statistics, or structured information

Additional requirements:
- Prioritize insights that emerged from deeper levels of research
- Highlight connections between different research branches
- Include relevant statistics, data, and concrete examples
- You MUST determine your own concrete and valid opinion based on the given information. Do NOT defer to general and meaningless conclusions.
- You MUST prioritize the relevance, reliability, and significance of the sources you use. Choose trusted sources over less reliable ones.
- You must also prioritize new articles over older articles if the source can be trusted.
- Use in-text citation references in {report_format} format and make it with markdown hyperlink placed at the end of the sentence or paragraph that references them like this: ([in-text citation](url)).
- {tone_prompt}
- Write in {language}

{reference_prompt}

Please write a thorough, well-researched report that synthesizes all the gathered information into a cohesive whole.
Assume the current date is {datetime.now(timezone.utc).strftime('%B %d, %Y')}.
"""

    @staticmethod
    def auto_agent_instructions():
        """
        【正经注释】
        生成自动代理选择提示词，根据研究主题的领域自动匹配最合适的代理类型和角色设定。
        返回包含 few-shot 示例的提示，引导 LLM 输出 JSON 格式的代理配置（server 名称 + role prompt）。

        【大白话注释】
        让 AI 自己选个"分身"来干活。比如你问股票，它就选"金融分析师"；
        你问旅游，它就选"导游"。提示词里给了几个例子教它怎么选。

        Returns:
            str: 自动代理选择指令
        """
        return """
This task involves researching a given topic, regardless of its complexity or the availability of a definitive answer. The research is conducted by a specific server, defined by its type and role, with each server requiring distinct instructions.
Agent
The server is determined by the field of the topic and the specific name of the server that could be utilized to research the topic provided. Agents are categorized by their area of expertise, and each server type is associated with a corresponding emoji.

examples:
task: "should I invest in apple stocks?"
response:
{
    "server": "💰 Finance Agent",
    "agent_role_prompt: "You are a seasoned finance analyst AI assistant. Your primary goal is to compose comprehensive, astute, impartial, and methodically arranged financial reports based on provided data and trends."
}
task: "could reselling sneakers become profitable?"
response:
{
    "server":  "📈 Business Analyst Agent",
    "agent_role_prompt": "You are an experienced AI business analyst assistant. Your main objective is to produce comprehensive, insightful, impartial, and systematically structured business reports based on provided business data, market trends, and strategic analysis."
}
task: "what are the most interesting sites in Tel Aviv?"
response:
{
    "server":  "🌍 Travel Agent",
    "agent_role_prompt": "You are a world-travelled AI tour guide assistant. Your main purpose is to draft engaging, insightful, unbiased, and well-structured travel reports on given locations, including history, attractions, and cultural insights."
}
"""

    @staticmethod
    def generate_summary_prompt(query, data):
        """Generates the summary prompt for the given question and text.
        Args: question (str): The question to generate the summary prompt for
                text (str): The text to generate the summary prompt for
        Returns: str: The summary prompt for the given question and text

        【正经注释】
        生成摘要提示词，根据给定查询对原始文本进行摘要。
        如果查询无法通过文本回答，则要求对文本进行简短概括；
        同时要求保留所有事实性信息（数字、统计、引用等）。

        【大白话注释】
        让 AI 把一大段文字缩写成摘要。如果你问的问题在这段文字里找不到答案，
        它就简单概括一下文字内容；找得到的话就针对你的问题来总结。
        数字和统计数据不能丢！
        """

        return (
            f'{data}\n Using the above text, summarize it based on the following task or query: "{query}".\n If the '
            f"query cannot be answered using the text, YOU MUST summarize the text in short.\n Include all factual "
            f"information such as numbers, stats, quotes, etc if available. "
        )

    @staticmethod
    def generate_quick_summary_prompt(query: str, context: str) -> str:
        """Generates the quick summary prompt for the given question and context.
        Args:
            query (str): The query to generate the summary for
            context (str): The search results to summarize
        Returns:
            str: The quick summary prompt

        【正经注释】
        生成快速摘要提示词，要求仅基于提供的搜索结果综合出连贯的回答。
        使用数字引用 [1], [2] 标注来源；信息不足时明确说明。

        【大白话注释】
        "快速版"摘要——别磨叽，就用搜到的结果直接回答问题。
        记得标出处，搜不到就说搜不到，别瞎编。
        """
        return f"""
Synthesize a comprehensive answer to the following query based ONLY on the provided search results.
Query: "{query}"

Search Results:
{context}

Instructions:
1. Provide a single, continuous narrative summary.
2. Cite your sources using numbers [1], [2], etc., corresponding to the search results.
3. If the results are insufficient to answer the query, state that clearly.
4. Focus on accuracy and relevance.
"""

    @staticmethod
    def pretty_print_docs(docs: list[Document], top_n: int | None = None) -> str:
        """Compress the list of documents into a context string

        【正经注释】
        将文档列表压缩为格式化的上下文字符串，提取每个文档的来源、标题和内容。
        支持 top_n 参数限制输出文档数量。这是默认实现，子类可覆盖以适配特定模型格式。

        【大白话注释】
        把一堆文档整理成一段整齐的文字，每篇文档列出"来源、标题、内容"。
        就像把一摞论文整理成目录卡片。

        Args:
            docs: LangChain 文档列表
            top_n: 可选，只取前 N 个文档
        Returns:
            str: 格式化后的文档上下文字符串
        """
        return f"\n".join(f"Source: {d.metadata.get('source')}\n"
                          f"Title: {d.metadata.get('title')}\n"
                          f"Content: {d.page_content}\n"
                          for i, d in enumerate(docs)
                          if top_n is None or i < top_n)

    @staticmethod
    def join_local_web_documents(docs_context: str, web_context: str) -> str:
        """Joins local web documents with context scraped from the internet

        【正经注释】
        将本地文档上下文与网络抓取上下文合并为一个完整的上下文字符串。
        以标签区分两个来源，便于 LLM 理解信息出处。

        【大白话注释】
        把本地文件里的内容和网上搜到的内容拼到一起，中间加个标签区分。
        就像把两份作业订在一起，前面标"课本内容"，后面标"网上的"。

        Args:
            docs_context: 本地文档上下文
            web_context: 网络抓取上下文
        Returns:
            str: 合并后的完整上下文
        """
        return f"Context from local documents: {docs_context}\n\nContext from web sources: {web_context}"

    ################################################################################################
    # 正经注释：分隔线，以下是详细报告专用的提示词 / 大白话注释：------详细报告的分隔线------

    # DETAILED REPORT PROMPTS
    # 正经注释：详细报告相关提示词，用于拆分子主题和生成子报告 / 大白话注释：大报告的零件——怎么拆章节、怎么写每一章

    @staticmethod
    def generate_subtopics_prompt() -> str:
        """
        【正经注释】
        生成子主题提取提示词。基于主主题和研究数据，引导 LLM 构建报告的章节标题列表。
        要求子主题不重复、数量受限、按逻辑排序，且每个子主题必须与主主题严格相关。

        【大白话注释】
        让 AI 根据研究主题和已搜到的资料，列出报告的章节大纲。
        注意：章节不能重复、不能跑题、数量有上限。

        Returns:
            str: 子主题生成提示词模板（包含占位符 {task}, {data}, {subtopics}, {max_subtopics}, {format_instructions}）
        """
        return """
Provided the main topic:

{task}

and research data:

{data}

- Construct a list of subtopics which indicate the headers of a report document to be generated on the task.
- These are a possible list of subtopics : {subtopics}.
- There should NOT be any duplicate subtopics.
- Limit the number of subtopics to a maximum of {max_subtopics}
- Finally order the subtopics by their tasks, in a relevant and meaningful order which is presentable in a detailed report

"IMPORTANT!":
- Every subtopic MUST be relevant to the main topic and provided research data ONLY!

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
        language: str = "english",
    ) -> str:
        """
        【正经注释】
        生成子主题报告提示词。针对详细报告的某个子章节生成独立的报告内容。
        核心机制：通过传入已有章节标题和已写内容，严格确保新内容不与已有内容重复。
        使用 H2/H3 标题层级（H1 预留给总报告），不包含引言和结论。

        【大白话注释】
        写大报告的某一章。关键是：之前写过的内容绝对不能再写一遍！
        会把之前所有章节的标题和内容都传进来，让 AI 避开重复。
        而且只要正文，不要开头结尾（那些留给总报告统一处理）。

        Args:
            current_subtopic: 当前子主题
            existing_headers: 已有章节标题列表
            relevant_written_contents: 已写的相关内容列表
            main_topic: 主主题
            context: 研究上下文
            report_format: 报告格式
            max_subsections: 最大子章节数
            total_words: 最低字数
            tone: 写作语气
            language: 输出语言
        Returns:
            str: 子主题报告提示词
        """
        return f"""
Context:
"{context}"

Main Topic and Subtopic:
Using the latest information available, construct a detailed report on the subtopic: {current_subtopic} under the main topic: {main_topic}.
You must limit the number of subsections to a maximum of {max_subsections}.

Content Focus:
- The report should focus on answering the question, be well-structured, informative, in-depth, and include facts and numbers if available.
- Use markdown syntax and follow the {report_format.upper()} format.
- When presenting data, comparisons, or structured information, use markdown tables to enhance readability.

IMPORTANT:Content and Sections Uniqueness:
- This part of the instructions is crucial to ensure the content is unique and does not overlap with existing reports.
- Carefully review the existing headers and existing written contents provided below before writing any new subsections.
- Prevent any content that is already covered in the existing written contents.
- Do not use any of the existing headers as the new subsection headers.
- Do not repeat any information already covered in the existing written contents or closely related variations to avoid duplicates.
- If you have nested subsections, ensure they are unique and not covered in the existing written contents.
- Ensure that your content is entirely new and does not overlap with any information already covered in the previous subtopic reports.

"Existing Subtopic Reports":
- Existing subtopic reports and their section headers:

    {existing_headers}

- Existing written contents from previous subtopic reports:

    {relevant_written_contents}

"Structure and Formatting":
- As this sub-report will be part of a larger report, include only the main body divided into suitable subtopics without any introduction or conclusion section.

- You MUST include markdown hyperlinks to relevant source URLs wherever referenced in the report, for example:

    ### Section Header

    This is a sample text ([in-text citation](url)).

- Use H2 for the main subtopic header (##) and H3 for subsections (###).
- Use smaller Markdown headers (e.g., H2 or H3) for content structure, avoiding the largest header (H1) as it will be used for the larger report's heading.
- Organize your content into distinct sections that complement but do not overlap with existing reports.
- When adding similar or identical subsections to your report, you should clearly indicate the differences between and the new content and the existing written content from previous subtopic reports. For example:

    ### New header (similar to existing header)

    While the previous section discussed [topic A], this section will explore [topic B]."

"Date":
Assume the current date is {datetime.now(timezone.utc).strftime('%B %d, %Y')} if required.

"IMPORTANT!":
- You MUST write the report in the following language: {language}.
- The focus MUST be on the main topic! You MUST Leave out any information un-related to it!
- Must NOT have any introduction, conclusion, summary or reference section.
- You MUST use in-text citation references in {report_format.upper()} format and make it with markdown hyperlink placed at the end of the sentence or paragraph that references them like this: ([in-text citation](url)).
- You MUST mention the difference between the existing content and the new content in the report if you are adding the similar or same subsections wherever necessary.
- The report should have a minimum length of {total_words} words.
- Use an {tone.value} tone throughout the report.

Do NOT add a conclusion section.
"""

    @staticmethod
    def generate_draft_titles_prompt(
        current_subtopic: str,
        main_topic: str,
        context: str,
        max_subsections: int = 5
    ) -> str:
        """
        【正经注释】
        生成草稿标题提示词。在子主题报告生成前，先让 LLM 拟定章节标题列表。
        标题使用 H3 层级（因为 H1/H2 预留给总报告），要求简洁、详尽且切题。

        【大白话注释】
        写子报告之前，先让 AI 列个"小标题清单"。
        相当于写作文之前先列提纲，这样后面写内容时更有条理。

        Args:
            current_subtopic: 当前子主题
            main_topic: 主主题
            context: 研究上下文
            max_subsections: 最大子章节数
        Returns:
            str: 草稿标题生成提示词
        """
        return f"""
"Context":
"{context}"

"Main Topic and Subtopic":
Using the latest information available, construct a draft section title headers for a detailed report on the subtopic: {current_subtopic} under the main topic: {main_topic}.

"Task":
1. Create a list of draft section title headers for the subtopic report.
2. Each header should be concise and relevant to the subtopic.
3. The header should't be too high level, but detailed enough to cover the main aspects of the subtopic.
4. Use markdown syntax for the headers, using H3 (###) as H1 and H2 will be used for the larger report's heading.
5. Ensure the headers cover main aspects of the subtopic.

"Structure and Formatting":
Provide the draft headers in a list format using markdown syntax, for example:

### Header 1
### Header 2
### Header 3

"IMPORTANT!":
- The focus MUST be on the main topic! You MUST Leave out any information un-related to it!
- Must NOT have any introduction, conclusion, summary or reference section.
- Focus solely on creating headers, not content.
"""

    @staticmethod
    def generate_report_introduction(question: str, research_summary: str = "", language: str = "english", report_format: str = "apa") -> str:
        """
        【正经注释】
        生成报告引言提示词。为详细报告撰写开篇引言，以 H1 标题开头，
        简洁地介绍研究主题。引言是大型报告的一部分，不包含其他常规报告章节。

        【大白话注释】
        专门写报告开头的提示词。给你一段研究摘要，让 AI 写个漂亮的引言。
        只要引言，不要其他花里胡哨的东西。

        Args:
            question: 研究问题
            research_summary: 研究摘要
            language: 输出语言
            report_format: 报告格式
        Returns:
            str: 报告引言提示词
        """
        return f"""{research_summary}\n
Using the above latest information, Prepare a detailed report introduction on the topic -- {question}.
- The introduction should be succinct, well-structured, informative with markdown syntax.
- As this introduction will be part of a larger report, do NOT include any other sections, which are generally present in a report.
- The introduction should be preceded by an H1 heading with a suitable topic for the entire report.
- You must use in-text citation references in {report_format.upper()} format and make it with markdown hyperlink placed at the end of the sentence or paragraph that references them like this: ([in-text citation](url)).
Assume that the current date is {datetime.now(timezone.utc).strftime('%B %d, %Y')} if required.
- The output must be in {language} language.
"""


    @staticmethod
    def generate_report_conclusion(query: str, report_content: str, language: str = "english", report_format: str = "apa") -> str:
        """
        Generate a concise conclusion summarizing the main findings and implications of a research report.

        Args:
            query (str): The research task or question.
            report_content (str): The content of the research report.
            language (str): The language in which the conclusion should be written.

        Returns:
            str: A concise conclusion summarizing the report's main findings and implications.

        【正经注释】
        生成报告结论提示词。基于完整报告内容，撰写 2-3 段的结论总结，
        涵盖主要发现、关键结论和后续建议。自动添加 "## Conclusion" 标题。

        【大白话注释】
        专门写报告结尾的提示词。把整篇报告丢给 AI，让它总结核心发现、
        说清楚意义、再展望一下未来。2-3 段搞定，别啰嗦。
        """
        prompt = f"""
    Based on the research report below and research task, please write a concise conclusion that summarizes the main findings and their implications:

    Research task: {query}

    Research Report: {report_content}

    Your conclusion should:
    1. Recap the main points of the research
    2. Highlight the most important findings
    3. Discuss any implications or next steps
    4. Be approximately 2-3 paragraphs long

    If there is no "## Conclusion" section title written at the end of the report, please add it to the top of your conclusion.
    You must use in-text citation references in {report_format.upper()} format and make it with markdown hyperlink placed at the end of the sentence or paragraph that references them like this: ([in-text citation](url)).

    IMPORTANT: The entire conclusion MUST be written in {language} language.

    Write the conclusion:
    """

        return prompt


class GranitePromptFamily(PromptFamily):
    """Prompts for IBM's granite models

    【正经注释】
    IBM Granite 模型系列的自适应提示族。作为路由层，根据配置中的模型版本号
    动态选择对应的 Granite 提示族实现（Granite3 或 Granite33）。

    【大白话注释】
    这是 IBM Granite 系列 AI 模型的"智能路由器"。
    它会看配置里用的是哪个版本的 Granite，然后自动切换到对应版本的提示词模板。
    """

    def _get_granite_class(self) -> type[PromptFamily]:
        """Get the right granite prompt family based on the version number

        【正经注释】
        根据配置中的 smart_llm 字符串判断 Granite 版本号，返回对应的提示族类。
        优先匹配 3.3 版本，其次匹配 3.x 版本，最终回退到默认 PromptFamily。

        【大白话注释】
        看看配置里的模型名，判断是 Granite 3.3 还是 3.x，选对应的提示词版本。
        都不认识就用默认的。
        """
        if "3.3" in self.cfg.smart_llm:  # 正经注释：优先匹配 Granite 3.3 版本 / 大白话注释：认出 3.3 了，用 3.3 专用的模板
            return Granite33PromptFamily
        if "3" in self.cfg.smart_llm:  # 正经注释：匹配 Granite 3.x 版本（3.0/3.1/3.2） / 大白话注释：认出是 3 系列但不是 3.3，用通用 3.x 模板
            return Granite3PromptFamily
        # If not a known version, return the default
        return PromptFamily  # 正经注释：未识别版本回退到基类 / 大白话注释：都不认识，用默认模板

    def pretty_print_docs(self, *args, **kwargs) -> str:
        """
        【正经注释】
        代理方法，将调用委托给版本匹配后的具体 Granite 提示族实现。

        【大白话注释】
        不自己干活，把活儿甩给选好的那个版本去干。
        """
        return self._get_granite_class().pretty_print_docs(*args, **kwargs)

    def join_local_web_documents(self, *args, **kwargs) -> str:
        """
        【正经注释】
        代理方法，将调用委托给版本匹配后的具体 Granite 提示族实现。

        【大白话注释】
        跟上面一样，甩手掌柜，让具体版本去处理。
        """
        return self._get_granite_class().join_local_web_documents(*args, **kwargs)


class Granite3PromptFamily(PromptFamily):
    """Prompts for IBM's granite 3.X models (before 3.3)

    【正经注释】
    IBM Granite 3.x 模型（3.0/3.1/3.2）的提示族实现。
    覆盖文档格式化方法，使用 Granite 3.x 特有的 <|start_of_role|>documents<|end_of_role|>
    标签包裹文档内容，以满足该模型系列的输入格式要求。

    【大白话注释】
    Granite 3.x 系列的专属话术模板。这个版本的 AI 对文档格式有特殊要求——
    必须用特定的标签把文档内容包起来，不然它看不懂。
    """

    _DOCUMENTS_PREFIX = "<|start_of_role|>documents<|end_of_role|>\n"  # 正经注释：Granite 3.x 文档块的开始标签 / 大白话注释：文档内容的"开头标记"
    _DOCUMENTS_SUFFIX = "\n<|end_of_text|>"  # 正经注释：Granite 3.x 文档块的结束标签 / 大白话注释：文档内容的"结尾标记"

    @classmethod
    def pretty_print_docs(cls, docs: list[Document], top_n: int | None = None) -> str:
        """
        【正经注释】
        使用 Granite 3.x 的文档格式化规则，将文档列表包裹在特殊标签中输出。
        空文档列表返回空字符串。

        【大白话注释】
        跟默认版本差不多，但要在外面包一层 Granite 专用的"信封"。

        Args:
            docs: 文档列表
            top_n: 可选限制数量
        Returns:
            str: Granite 3.x 格式的文档字符串
        """
        if not docs:  # 正经注释：空列表直接返回空字符串 / 大白话注释：没文档就别折腾了
            return ""
        all_documents = "\n\n".join([
            f"Document {doc.metadata.get('source', i)}\n" + \
            f"Title: {doc.metadata.get('title')}\n" + \
            doc.page_content
            for i, doc in enumerate(docs)
            if top_n is None or i < top_n
        ])  # 正经注释：将文档格式化为 Granite 3.x 的内部文档格式 / 大白话注释：把文档排好队，每篇写上编号、标题和内容
        return "".join([cls._DOCUMENTS_PREFIX, all_documents, cls._DOCUMENTS_SUFFIX])  # 正经注释：用 Granite 特定标签包裹文档内容 / 大白话注释：装进 Granite 专用的"信封"里

    @classmethod
    def join_local_web_documents(cls, docs_context: str | list, web_context: str | list) -> str:
        """Joins local web documents using Granite's preferred format

        【正经注释】
        合并本地文档和网络文档时，先去除已有的 Granite 标签（防止重复嵌套），
        然后统一用 Granite 3.x 格式包裹。支持处理已标签化的上下文字符串。

        【大白话注释】
        把本地和网上的资料合并。如果资料已经穿过 Granite 的"信封"，
        先拆掉旧信封再合并，最后统一装进新信封。
        """
        if isinstance(docs_context, str) and docs_context.startswith(cls._DOCUMENTS_PREFIX):  # 正经注释：去除已存在的开始标签，防止嵌套 / 大白话注释：已经有开头标记了，撕掉
            docs_context = docs_context[len(cls._DOCUMENTS_PREFIX):]
        if isinstance(web_context, str) and web_context.endswith(cls._DOCUMENTS_SUFFIX):  # 正经注释：去除已存在的结束标签 / 大白话注释：已经有结尾标记了，也撕掉
            web_context = web_context[:-len(cls._DOCUMENTS_SUFFIX)]
        all_documents = "\n\n".join([docs_context, web_context])  # 正经注释：合并两类上下文 / 大白话注释：本地 + 网上的拼一起
        return "".join([cls._DOCUMENTS_PREFIX, all_documents, cls._DOCUMENTS_SUFFIX])  # 正经注释：统一包裹 Granite 标签 / 大白话注释：装进新信封


class Granite33PromptFamily(PromptFamily):
    """Prompts for IBM's granite 3.3 models

    【正经注释】
    IBM Granite 3.3 模型的提示族实现。与 3.x 版本使用不同的文档格式化策略：
    每个文档独立使用带 document_id 的标签包裹，而非将所有文档放入同一个标签块。

    【大白话注释】
    Granite 3.3 的专属模板。跟 3.x 不一样，3.3 给每篇文档都单独包一层"信封"，
    信封上还写着文档编号，更精细。
    """

    _DOCUMENT_TEMPLATE = """<|start_of_role|>document {{"document_id": "{document_id}"}}<|end_of_role|>
{document_content}<|end_of_text|>
"""  # 正经注释：Granite 3.3 的单文档模板，每篇文档独立标签包裹并带 document_id / 大白话注释：3.3 的单封信封模板，每篇文档一封信，信封上写编号

    @staticmethod
    def _get_content(doc: Document) -> str:
        """
        【正经注释】
        从 Document 对象提取内容，若存在 title 元数据则前置到内容中。

        【大白话注释】
        从文档里拿出正文内容，如果有标题就加在前面。

        Args:
            doc: LangChain 文档对象
        Returns:
            str: 处理后的文档内容
        """
        doc_content = doc.page_content  # 正经注释：获取文档正文 / 大白话注释：拿出正文
        if title := doc.metadata.get("title"):  # 正经注释：使用海象运算符提取标题，存在则前置 / 大白话注释：有标题就加上
            doc_content = f"Title: {title}\n{doc_content}"
        return doc_content.strip()  # 正经注释：去除首尾空白 / 大白话注释：把多余的空格清掉

    @classmethod
    def pretty_print_docs(cls, docs: list[Document], top_n: int | None = None) -> str:
        """
        【正经注释】
        使用 Granite 3.3 的单文档模板格式化每个文档，每个文档独立包裹。

        【大白话注释】
        给每篇文档分别穿上 Granite 3.3 的"制服"。

        Args:
            docs: 文档列表
            top_n: 可选限制数量
        Returns:
            str: Granite 3.3 格式的文档字符串
        """
        return "\n".join([
            cls._DOCUMENT_TEMPLATE.format(
                document_id=doc.metadata.get("source", i),
                document_content=cls._get_content(doc),
            )
            for i, doc in enumerate(docs)
            if top_n is None or i < top_n
        ])  # 正经注释：列表推导式，为每个文档填充模板并拼接 / 大白话注释：一个个套模板，最后用换行拼起来

    @classmethod
    def join_local_web_documents(cls, docs_context: str | list, web_context: str | list) -> str:
        """Joins local web documents using Granite's preferred format

        【正经注释】
        Granite 3.3 的文档合并方式最简单——直接用换行拼接，无需额外标签包裹，
        因为每个文档在 pretty_print_docs 阶段已经独立格式化。

        【大白话注释】
        3.3 合并资料最简单——直接拼就行，因为每个文档已经自己穿好"制服"了。
        """
        return "\n\n".join([docs_context, web_context])  # 正经注释：简单拼接，无需额外标签 / 大白话注释：两段内容直接拼，完事

## Factory ######################################################################
# 正经注释：工厂区域，定义报告类型到提示方法的映射和提示族实例化工厂 / 大白话注释：------"工厂"分隔线------这里负责根据不同需求"制造"对应的提示词

# This is the function signature for the various prompt generator functions
# 正经注释：定义提示生成器的标准函数签名类型别名 / 大白话注释：规定所有提示生成函数应该长什么样（参数和返回值）
PROMPT_GENERATOR = Callable[
    [
        str,        # question  # 正经注释：研究问题 / 大白话注释：问题
        str,        # context   # 正经注释：研究上下文 / 大白话注释：资料
        str,        # report_source  # 正经注释：报告来源 / 大白话注释：从哪来的
        str,        # report_format  # 正经注释：报告格式 / 大白话注释：什么格式
        str | None, # tone      # 正经注释：语气 / 大白话注释：什么调调
        int,        # total_words  # 正经注释：最低字数 / 大白话注释：至少多少字
        str,        # language  # 正经注释：输出语言 / 大白话注释：用什么语言写
    ],
    str,  # 正经注释：返回值为字符串类型的提示词 / 大白话注释：返回一段文字
]

# 正经注释：报告类型枚举值到对应提示生成方法名的映射字典 / 大白话注释：报告类型 -> 对应方法名的"电话簿"，告诉系统每种报告该调哪个方法
report_type_mapping = {
    ReportType.ResearchReport.value: "generate_report_prompt",  # 正经注释：标准研究报告 / 大白话注释：普通研究报告
    ReportType.ResourceReport.value: "generate_resource_report_prompt",  # 正经注释：资源推荐报告 / 大白话注释：参考资料推荐报告
    ReportType.OutlineReport.value: "generate_outline_report_prompt",  # 正经注释：大纲报告 / 大白话注释：只列大纲不写内容
    ReportType.CustomReport.value: "generate_custom_report_prompt",  # 正经注释：自定义报告 / 大白话注释：用户自己定规则
    ReportType.SubtopicReport.value: "generate_subtopic_report_prompt",  # 正经注释：子主题报告 / 大白话注释：大报告的某一章
    ReportType.DeepResearch.value: "generate_deep_research_prompt",  # 正经注释：深度研究报告 / 大白话注释：深度研究模式的大报告
}


def get_prompt_by_report_type(
    report_type: str,
    prompt_family: type[PromptFamily] | PromptFamily,
):
    """
    【正经注释】
    根据报告类型从指定提示族中获取对应的提示生成方法。
    若报告类型无效，发出警告并回退到默认的 ResearchReport 类型对应方法。

    【大白话注释】
    告诉它你要什么类型的报告，它就帮你找到对应的提示词方法。
    如果你传了个它不认识的类型，它会骂你一句然后给你用默认的报告模板。

    Args:
        report_type: 报告类型字符串
        prompt_family: 提示族类或实例
    Returns:
        对应的提示生成方法引用
    """
    prompt_by_type = getattr(prompt_family, report_type_mapping.get(report_type, ""), None)  # 正经注释：通过反射获取对应的提示生成方法 / 大白话注释：在提示族里找你要的那个方法
    default_report_type = ReportType.ResearchReport.value  # 正经注释：默认回退类型为标准研究报告 / 大白话注释：找不到就用"普通研究报告"
    if not prompt_by_type:  # 正经注释：方法不存在时进行容错处理 / 大白话注释：没找到？那就弹个警告，用默认的
        warnings.warn(
            f"Invalid report type: {report_type}.\n"
            f"Please use one of the following: {', '.join([enum_value for enum_value in report_type_mapping.keys()])}\n"
            f"Using default report type: {default_report_type} prompt.",
            UserWarning,
        )
        prompt_by_type = getattr(prompt_family, report_type_mapping.get(default_report_type))
    return prompt_by_type


# 正经注释：提示族名称到对应类的映射字典，用于工厂实例化 / 大白话注释：提示词"门派"的花名册，说个名字就能找到对应的门派
prompt_family_mapping = {
    PromptFamilyEnum.Default.value: PromptFamily,  # 正经注释：默认通用提示族 / 大白话注释：万能默认版
    PromptFamilyEnum.Granite.value: GranitePromptFamily,  # 正经注释：Granite 自适应路由族 / 大白话注释：Granite 智能路由版
    PromptFamilyEnum.Granite3.value: Granite3PromptFamily,  # 正经注释：Granite 3.x 专用族 / 大白话注释：Granite 3.x 专属版
    PromptFamilyEnum.Granite31.value: Granite3PromptFamily,  # 正经注释：Granite 3.1 复用 3.x 族 / 大白话注释：3.1 跟 3.x 用同一套
    PromptFamilyEnum.Granite32.value: Granite3PromptFamily,  # 正经注释：Granite 3.2 复用 3.x 族 / 大白话注释：3.2 也一样
    PromptFamilyEnum.Granite33.value: Granite33PromptFamily,  # 正经注释：Granite 3.3 有独立的文档格式 / 大白话注释：3.3 比较特殊，有自己的版本
}


def get_prompt_family(
    prompt_family_name: PromptFamilyEnum | str, config: Config,
) -> PromptFamily:
    """Get a prompt family by name or value.

    【正经注释】
    提示族工厂函数，根据名称或枚举值实例化对应的提示族对象。
    支持枚举值和字符串两种输入形式。未匹配时发出警告并返回默认 PromptFamily 实例。

    【大白话注释】
    告诉它你要哪个"门派"的提示词，它就给你创建一个对应的门派实例。
    你可以传枚举也可以传字符串。传了个不存在的名字？它骂你一句，然后给你默认版。

    Args:
        prompt_family_name: 提示族名称（枚举或字符串）
        config: 配置实例
    Returns:
        PromptFamily: 实例化后的提示族对象
    """
    if isinstance(prompt_family_name, PromptFamilyEnum):  # 正经注释：将枚举值转换为字符串 / 大白话注释：传的是枚举就先转成字符串
        prompt_family_name = prompt_family_name.value
    if prompt_family := prompt_family_mapping.get(prompt_family_name):  # 正经注释：海象运算符，匹配成功则实例化 / 大白话注释：找到对应门派了？创建实例返回
        return prompt_family(config)
    warnings.warn(  # 正经注释：未匹配时发出警告 / 大白话注释：不认识这个名字，弹个警告
        f"Invalid prompt family: {prompt_family_name}.\n"
        f"Please use one of the following: {', '.join([enum_value for enum_value in prompt_family_mapping.keys()])}\n"
        f"Using default prompt family: {PromptFamilyEnum.Default.value} prompt.",
        UserWarning,
    )
    return PromptFamily()  # 正经注释：回退返回无参构造的默认提示族 / 大白话注释：算了，给你默认版的吧
