"""
详细报告模块（detailed_report）

【正经注释】
本模块实现了 DetailedReport 类，提供多步骤的详细报告生成功能。
该类的核心流程为：初始研究 -> 子话题提取 -> 子话题逐一研究 -> 汇总构建报告。
支持全局上下文共享、已访问 URL 去重、已写章节追踪、MCP 扩展协议等特性，
能够生成包含引言、目录、多子话题正文和结论的完整结构化报告。

【大白话注释】
这个文件是"豪华版报告生成器"，比 BasicReport 复杂多了。它的工作流程是：
先大致研究一下你的问题 -> 把大问题拆成几个小话题 -> 每个小话题分别深入研究 ->
最后把所有小话题的报告拼在一起，加上目录和结论，生成一份超详细的报告。
适合那种需要深入分析、多角度探讨的复杂问题。
"""

import asyncio  # 正经注释：Python 异步编程核心库，用于并发执行多个研究任务 / 大白话注释：异步编程用的，让多个任务可以同时跑
import hashlib  # 正经注释：提供哈希算法，用于生成唯一研究 ID / 大白话注释：给每次研究生成一个唯一编号
import time  # 正经注释：提供时间功能，用于生成带时间戳的研究 ID / 大白话注释：拿时间信息，让编号带时间
from typing import List, Dict, Set, Optional, Any  # 正经注释：导入类型提示工具，增强代码可读性和类型安全性 / 大白话注释：类型标注用的，告诉 Python 每个变量是啥类型
from fastapi import WebSocket  # 正经注释：导入 FastAPI 的 WebSocket 类，用于实时向前端推送研究进度 / 大白话注释：跟前端"打电话"用的，实时通知进展

from gpt_researcher import GPTResearcher  # 正经注释：导入核心研究器类，是执行研究和生成报告的主引擎 / 大白话注释：把"研究大脑"请过来，所有的搜索和分析都是它干的


class DetailedReport:
    """
    详细报告生成类

    【正经注释】
    实现多步骤的详细报告生成流程。通过初始研究识别子话题，然后为每个子话题
    创建独立的研究器实例进行深度研究，最终汇总为包含引言、目录、多章节正文
    和结论的完整报告。支持全局上下文共享、去重和跨子话题引用。

    【大白话注释】
    这个类就是"豪华版报告"的大管家。它的工作方式是：
    先对整个问题做个初步研究 -> 拆分出若干子话题 -> 每个子话题单独派一个"研究员"去深入调查 ->
    把所有子话题的报告拼在一起，加上开头和结尾，组成一份完整的大报告。
    好处是每个子话题都能深入研究，不会浅尝辄止。
    """

    def __init__(
        self,
        query: str,  # 正经注释：用户的原始查询字符串 / 大白话注释：你想研究的核心问题
        report_type: str,  # 正经注释：报告类型标识 / 大白话注释：报告类型
        report_source: str,  # 正经注释：数据来源类型，如 web、local / 大白话注释：资料从哪儿来——网上搜还是本地找
        source_urls: List[str] = [],  # 正经注释：用户预设的参考 URL 列表 / 大白话注释：你已经知道的有用网址
        document_urls: List[str] = [],  # 正经注释：本地文档路径列表 / 大白话注释：本地文档文件路径
        query_domains: List[str] = [],  # 正经注释：限制搜索范围的域名列表 / 大白话注释：只在这些网站里搜
        config_path: str = None,  # 正经注释：配置文件路径 / 大白话注释：配置文件在哪
        tone: Any = "",  # 正经注释：报告语气风格 / 大白话注释：用啥语气写
        websocket: WebSocket = None,  # 正经注释：WebSocket 连接，用于实时推送 / 大白话注释：跟前端通话的"电话线"
        subtopics: List[Dict] = [],  # 正经注释：预设的子话题列表 / 大白话注释：你已经想好的子话题，不用 AI 自动拆
        headers: Optional[Dict] = None,  # 正经注释：自定义 HTTP 请求头 / 大白话注释：额外的请求头信息
        complement_source_urls: bool = False,  # 正经注释：是否补充源 URL 的标志 / 大白话注释：要不要自动补充更多参考资料链接
        mcp_configs=None,  # 正经注释：MCP 服务配置 / 大白话注释：MCP 扩展工具的配置
        mcp_strategy=None,  # 正经注释：MCP 调用策略 / 大白话注释：MCP 工具怎么调的策略
        max_search_results=None,  # 正经注释：每次搜索最大结果数 / 大白话注释：每次搜最多返回多少条
    ):
        self.query = query  # 正经注释：保存查询字符串 / 大白话注释：记住用户的问题
        self.report_type = report_type  # 正经注释：保存报告类型 / 大白话注释：记住报告类型
        self.report_source = report_source  # 正经注释：保存数据来源 / 大白话注释：记住资料来源
        self.source_urls = source_urls  # 正经注释：保存预设 URL / 大白话注释：记住用户给的网址
        self.document_urls = document_urls  # 正经注释：保存文档路径 / 大白话注释：记住本地文档路径
        self.query_domains = query_domains  # 正经注释：保存域名过滤 / 大白话注释：记住网站限制
        self.config_path = config_path  # 正经注释：保存配置路径 / 大白话注释：记住配置文件位置
        self.tone = tone  # 正经注释：保存语气设置 / 大白话注释：记住语气风格
        self.websocket = websocket  # 正经注释：保存 WebSocket / 大白话注释：记住"电话线"
        self.subtopics = subtopics  # 正经注释：保存子话题列表 / 大白话注释：记住预设子话题
        self.headers = headers or {}  # 正经注释：保存请求头，默认空字典 / 大白话注释：记住请求头
        self.complement_source_urls = complement_source_urls  # 正经注释：保存是否补充源 URL 的标志 / 大白话注释：记住要不要自动补链接
        self.max_search_results = max_search_results  # 正经注释：保存最大搜索结果数 / 大白话注释：记住搜多少条

        # Generate a unique research ID for this report
        self.research_id = self._generate_research_id(query)  # 正经注释：生成唯一研究标识 / 大白话注释：给这次研究起个唯一编号

        # Initialize researcher with optional MCP parameters
        gpt_researcher_params = {  # 正经注释：构建 GPTResearcher 初始化参数字典 / 大白话注释：把参数打包，准备传给"研究大脑"
            "query": self.query,  # 正经注释：传入查询 / 大白话注释：把问题传过去
            "query_domains": self.query_domains,  # 正经注释：传入域名过滤 / 大白话注释：把网站限制传过去
            "report_type": "research_report",  # 正经注释：内部使用 research_report 类型进行初始研究 / 大白话注释：初始研究用标准研究类型
            "report_source": self.report_source,  # 正经注释：传入数据来源 / 大白话注释：把资料来源传过去
            "source_urls": self.source_urls,  # 正经注释：传入预设 URL / 大白话注释：把网址传过去
            "document_urls": self.document_urls,  # 正经注释：传入文档路径 / 大白话注释：把文档路径传过去
            "config_path": self.config_path,  # 正经注释：传入配置路径 / 大白话注释：把配置传过去
            "tone": self.tone,  # 正经注释：传入语气设置 / 大白话注释：把语气传过去
            "websocket": self.websocket,  # 正经注释：传入 WebSocket / 大白话注释：把"电话线"接上
            "headers": self.headers,  # 正经注释：传入请求头 / 大白话注释：把请求头传过去
            "complement_source_urls": self.complement_source_urls,  # 正经注释：传入是否补充源 URL / 大白话注释：告诉它要不要自动补链接
        }

        # Add MCP parameters if provided
        if mcp_configs is not None:  # 正经注释：如果提供了 MCP 配置则加入参数 / 大白话注释：有 MCP 配置就带上
            gpt_researcher_params["mcp_configs"] = mcp_configs
        if mcp_strategy is not None:  # 正经注释：如果提供了 MCP 策略则加入参数 / 大白话注释：有 MCP 策略也带上
            gpt_researcher_params["mcp_strategy"] = mcp_strategy

        self.gpt_researcher = GPTResearcher(**gpt_researcher_params)  # 正经注释：初始化主研究器实例 / 大白话注释：创建"研究大脑"主实例

        # Override max_search_results_per_query if provided by user
        if max_search_results is not None:  # 正经注释：覆盖默认的最大搜索结果数 / 大白话注释：用户说了搜多少就搜多少
            self.gpt_researcher.cfg.max_search_results_per_query = int(max_search_results)
        self.existing_headers: List[Dict] = []  # 正经注释：追踪已写子话题的标题结构，防止重复 / 大白话注释：已经写过的章节标题，防止写重复
        self.global_context: List[str] = []  # 正经注释：跨子话题共享的研究上下文 / 大白话注释：所有子话题共享的"知识库"，避免重复研究
        self.global_written_sections: List[str] = []  # 正经注释：所有已写章节内容的追踪列表 / 大白话注释：已经写好的内容，方便后面参考不重复
        self.global_urls: Set[str] = set(  # 正经注释：所有已访问 URL 的去重集合 / 大白话注释：已经访问过的网址，避免重复访问
            self.source_urls) if self.source_urls else set()

    def _generate_research_id(self, query: str) -> str:
        """
        生成唯一研究标识

        【正经注释】
        基于当前时间戳和查询字符串的 MD5 哈希前 8 位组合生成唯一 ID。
        与 BasicReport 使用不同的前缀 "detailed_" 以区分报告类型。

        【大白话注释】
        给每次详细研究搞一个独一无二的编号。用时间戳 + 问题的哈希值拼起来，
        前缀用 "detailed_" 开头，一看就知道是详细报告。

        Args:
            query: 用户查询字符串
        Returns:
            格式为 detailed_{时间戳}_{哈希} 的唯一 ID
        """
        timestamp = str(int(time.time()))  # 正经注释：获取当前时间戳 / 大白话注释：拿到当前时间
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]  # 正经注释：计算查询的 MD5 哈希并截取前 8 位 / 大白话注释：把问题变成短代码
        return f"detailed_{timestamp}_{query_hash}"  # 正经注释：拼接生成详细报告的研究 ID / 大白话注释：把前缀、时间、哈希拼在一起

    async def run(self) -> str:
        """
        执行完整的多步骤详细报告生成流程

        【正经注释】
        依次执行以下步骤：
        1. 初始研究：获取全局上下文和已访问 URL
        2. 子话题提取：基于研究结果识别并提取子话题
        3. 撰写引言：生成报告的开篇介绍
        4. 子话题报告：逐一研究每个子话题并生成子报告
        5. 构建最终报告：组合引言、目录、正文和结论

        【大白话注释】
        详细报告的"总指挥"方法，按顺序执行以下流程：
        先初步研究 -> 拆分子话题 -> 写开头 -> 每个子话题分别研究写报告 ->
        最后把所有内容拼成一份完整的大报告。

        Returns:
            str: 完整的详细报告文本（Markdown 格式）
        """
        await self._initial_research()  # 正经注释：第一步，执行初始研究获取全局上下文 / 大白话注释：先做个大概的研究，摸清底
        subtopics = await self._get_all_subtopics()  # 正经注释：第二步，从研究结果中提取子话题列表 / 大白话注释：把大问题拆成几个小话题
        report_introduction = await self.gpt_researcher.write_introduction()  # 正经注释：第三步，生成报告引言 / 大白话注释：写个漂亮的开头
        _, report_body = await self._generate_subtopic_reports(subtopics)  # 正经注释：第四步，为每个子话题生成子报告并拼接正文 / 大白话注释：每个小话题分别研究并写成小报告，拼在一起
        self.gpt_researcher.visited_urls.update(self.global_urls)  # 正经注释：将全局访问的 URL 合并到主研究器中 / 大白话注释：把所有访问过的网址汇总
        report = await self._construct_detailed_report(report_introduction, report_body)  # 正经注释：第五步，构建包含目录和结论的最终报告 / 大白话注释：把开头、目录、正文、结尾拼成完整报告
        return report  # 正经注释：返回最终报告 / 大白话注释：把做好的报告交出去

    async def _initial_research(self) -> None:
        """
        执行初始研究

        【正经注释】
        调用主研究器进行初始研究，获取研究上下文和已访问 URL。
        这些信息将作为后续子话题研究的全局共享基础。

        【大白话注释】
        先让"研究大脑"把整体问题研究一遍，搜到的资料和访问过的网址都记下来。
        这些信息后面研究子话题的时候可以复用，不用重复搜。
        """
        await self.gpt_researcher.conduct_research()  # 正经注释：执行初始研究，包括查询规划和信息检索 / 大白话注释：让研究大脑去搜资料
        self.global_context = self.gpt_researcher.context  # 正经注释：将研究上下文保存为全局共享数据 / 大白话注释：把搜到的资料存到"公共知识库"里
        self.global_urls = self.gpt_researcher.visited_urls  # 正经注释：将已访问 URL 保存为全局数据 / 大白话注释：把访问过的网址都记下来

    async def _get_all_subtopics(self) -> List[Dict]:
        """
        获取所有子话题

        【正经注释】
        调用主研究器的 get_subtopics 方法，基于初始研究结果让 LLM 提取子话题。
        每个子话题包含一个 task 字段，描述该子话题的研究任务。
        如果返回数据格式异常，打印警告信息。

        【大白话注释】
        让 AI 根据刚才的初步研究结果，把大问题拆成几个小话题。
        每个小话题就是一个"研究任务"，后面会分别派"研究员"去调查。
        如果 AI 返回的格式不对，就打印个警告。

        Returns:
            List[Dict]: 子话题列表，每个元素为 {"task": "子话题描述"}
        """
        subtopics_data = await self.gpt_researcher.get_subtopics()  # 正经注释：调用主研究器获取子话题数据 / 大白话注释：让 AI 把大问题拆成小话题

        all_subtopics = []  # 正经注释：初始化子话题列表 / 大白话注释：准备一个空列表来装子话题
        if subtopics_data and subtopics_data.subtopics:  # 正经注释：检查返回数据是否包含有效的子话题 / 大白话注释：看看 AI 有没有成功拆出子话题
            for subtopic in subtopics_data.subtopics:  # 正经注释：遍历每个子话题对象 / 大白话注释：一个一个看
                all_subtopics.append({"task": subtopic.task})  # 正经注释：提取子话题的任务描述并加入列表 / 大白话注释：把每个子话题的研究任务记下来
        else:
            print(f"Unexpected subtopics data format: {subtopics_data}")  # 正经注释：数据格式异常时打印警告 / 大白话注释：格式不对？打印出来让人看看怎么回事

        return all_subtopics  # 正经注释：返回完整的子话题列表 / 大白话注释：把子话题列表交出去

    async def _generate_subtopic_reports(self, subtopics: List[Dict]) -> tuple:
        """
        为所有子话题生成研究报告

        【正经注释】
        依次遍历子话题列表，为每个子话题调用 _get_subtopic_report 进行研究。
        将所有非空的子话题报告收集并拼接为完整的报告正文。
        返回子话题报告列表和拼接后的正文文本。

        【大白话注释】
        一个一个子话题地去研究，把每个子话题的研究报告收集起来。
        如果某个子话题研究成功写出了报告，就把内容加到正文里。
        最后返回两样东西：所有子报告的列表 + 拼好的大正文。

        Args:
            subtopics: 子话题列表
        Returns:
            tuple: (子话题报告列表, 拼接后的报告正文文本)
        """
        subtopic_reports = []  # 正经注释：存储所有子话题报告结果的列表 / 大白话注释：准备一个空列表装子报告
        subtopics_report_body = ""  # 正经注释：拼接后的报告正文文本 / 大白话注释：准备一个空字符串拼正文

        for subtopic in subtopics:  # 正经注释：遍历每个子话题 / 大白话注释：一个一个子话题来
            result = await self._get_subtopic_report(subtopic)  # 正经注释：研究当前子话题并获取报告 / 大白话注释：让研究员去调查这个子话题
            if result["report"]:  # 正经注释：检查是否成功生成了报告内容 / 大白话注释：看看有没有写出东西来
                subtopic_reports.append(result)  # 正经注释：将有效结果加入报告列表 / 大白话注释：写出来了就收集起来
                subtopics_report_body += f"\n\n\n{result['report']}"  # 正经注释：将报告内容追加到正文，用换行分隔 / 大白话注释：把内容拼到正文后面

        return subtopic_reports, subtopics_report_body  # 正经注释：返回报告列表和正文 / 大白话注释：把收集好的结果交出去

    def _hashable_context(self, input_context: List[str] | List[dict]):
        """
        将上下文转换为可哈希的字符串列表

        【正经注释】
        将上下文数据统一转换为字符串列表，确保每个元素都是可哈希的。
        支持处理纯字符串和字典格式（来自 MCP 服务）的上下文数据。
        字典格式会提取 title 和 body/content 字段拼接为字符串。

        【大白话注释】
        上下文里可能有各种格式的数据——有纯文字，也有字典（MCP 工具返回的）。
        这个方法就是把所有数据都变成字符串，方便后面做去重。
        字典的话就把标题和内容拼在一起变成文字。

        Args:
            input_context: 原始上下文数据列表（可能包含字符串或字典）
        Returns:
            List[str]: 统一转换为字符串后的上下文列表
        """
        # Convert context to strings to ensure hashability (handle both strings and dicts from MCP)
        context_items = []  # 正经注释：初始化结果列表 / 大白话注释：准备一个空列表装转换后的结果

        for item in input_context:  # 正经注释：遍历每条上下文数据 / 大白话注释：逐个处理
            if isinstance(item, dict):  # 正经注释：处理字典格式的上下文（通常来自 MCP 服务） / 大白话注释：如果是字典就特殊处理
                # Convert dict context to string format
                title = item.get("title", "No title")  # 正经注释：提取标题字段，默认为 "No title" / 大白话注释：拿出标题
                content = item.get("body", item.get("content", ""))  # 正经注释：提取内容字段，优先取 body，其次取 content / 大白话注释：拿出正文内容
                context_str = f"Title: {title}\nContent: {content}"  # 正经注释：拼接为标准格式的字符串 / 大白话注释：把标题和内容拼成一段文字
                context_items.append(context_str)  # 正经注释：加入结果列表 / 大白话注释：收集起来
            else:
                context_items.append(str(item))  # 正经注释：非字典类型直接转为字符串 / 大白话注释：普通文字就直接转成字符串收起来

        return context_items  # 正经注释：返回转换后的字符串列表 / 大白话注释：把转换好的结果交出去

    async def _get_subtopic_report(self, subtopic: Dict) -> Dict[str, str]:
        """
        获取单个子话题的研究报告

        【正经注释】
        为指定子话题创建独立的 GPTResearcher 实例进行深度研究。
        流程包括：初始化子话题研究器 -> 继承全局上下文 -> 执行研究 ->
        提取草稿标题 -> 查找相关已写内容 -> 生成报告 -> 更新全局状态。
        研究结果会更新全局上下文、已写章节和已访问 URL。

        【大白话注释】
        这是每个子话题的"专职研究员"。流程是：
        先创建一个新的研究器 -> 把之前搜到的资料传给它 -> 让它去深入研究 ->
        看看它打算写哪些小节 -> 找找之前有没有写过类似的内容 ->
        写出这个子话题的报告 -> 把新搜到的资料和访问的网址都更新到公共库里。

        Args:
            subtopic: 子话题字典，包含 "task" 字段
        Returns:
            Dict[str, str]: 包含 "topic"（子话题信息）和 "report"（报告文本）的字典
        """
        current_subtopic_task = subtopic.get("task")  # 正经注释：提取子话题的研究任务描述 / 大白话注释：看看这个子话题要研究啥
        subtopic_assistant = GPTResearcher(  # 正经注释：为当前子话题创建独立的研究器实例 / 大白话注释：给这个子话题派一个专门的"研究员"
            query=current_subtopic_task,  # 正经注释：设置子话题查询 / 大白话注释：告诉研究员研究什么
            query_domains=self.query_domains,  # 正经注释：继承域名过滤配置 / 大白话注释：继承网站限制
            report_type="subtopic_report",  # 正经注释：使用子话题报告类型 / 大白话注释：告诉它写的是"子话题报告"
            report_source=self.report_source,  # 正经注释：继承数据来源配置 / 大白话注释：继承资料来源
            websocket=self.websocket,  # 正经注释：继承 WebSocket 连接 / 大白话注释：接上"电话线"
            headers=self.headers,  # 正经注释：继承请求头 / 大白话注释：带上请求头
            parent_query=self.query,  # 正经注释：传入父查询，用于保持研究的连贯性 / 大白话注释：告诉它"大老板"的问题是什么
            subtopics=self.subtopics,  # 正经注释：传入子话题列表 / 大白话注释：告诉它总共有哪些子话题
            visited_urls=self.global_urls,  # 正经注释：传入已访问 URL 集合，避免重复访问 / 大白话注释：把之前访问过的网址给它，别重复访问
            agent=self.gpt_researcher.agent,  # 正经注释：继承主研究器的 agent 配置 / 大白话注释：继承"研究员类型"
            role=self.gpt_researcher.role,  # 正经注释：继承主研究器的角色设定 / 大白话注释：继承"角色扮演"
            tone=self.tone,  # 正经注释：继承语气设置 / 大白话注释：继承写作风格
            complement_source_urls=self.complement_source_urls,  # 正经注释：继承是否补充源 URL / 大白话注释：继承要不要补链接
            source_urls=self.source_urls,  # 正经注释：传入预设 URL / 大白话注释：把用户给的网址传过去
            # Propagate MCP configuration so follow-up researchers can use MCP
            mcp_configs=self.gpt_researcher.mcp_configs,  # 正经注释：继承 MCP 配置 / 大白话注释：把 MCP 工具配置也带上
            mcp_strategy=self.gpt_researcher.mcp_strategy  # 正经注释：继承 MCP 策略 / 大白话注释：把 MCP 调用策略也带上
        )

        # Propagate max_search_results override to subtopic researcher
        if self.max_search_results is not None:  # 正经注释：将最大搜索结果数覆盖传递给子话题研究器 / 大白话注释：告诉子研究员每次搜多少条
            subtopic_assistant.cfg.max_search_results_per_query = int(self.max_search_results)

        subtopic_assistant.context = list(set(self._hashable_context(self.global_context)))  # 正经注释：将去重后的全局上下文设置给子话题研究器 / 大白话注释：把公共知识库的资料（去重后）给子研究员
        await subtopic_assistant.conduct_research()  # 正经注释：执行子话题研究 / 大白话注释：让子研究员去搜索资料

        draft_section_titles = await subtopic_assistant.get_draft_section_titles(current_subtopic_task)  # 正经注释：获取子话题的草稿章节标题 / 大白话注释：看看子研究员打算写哪些章节

        if not isinstance(draft_section_titles, str):  # 正经注释：确保草稿标题为字符串格式 / 大白话注释：如果不是文字就转成文字
            draft_section_titles = str(draft_section_titles)

        parse_draft_section_titles = self.gpt_researcher.extract_headers(draft_section_titles)  # 正经注释：解析草稿标题中的各级标题结构 / 大白话注释：把标题结构拆出来
        parse_draft_section_titles_text = [header.get(  # 正经注释：提取标题的纯文本内容 / 大白话注释：把标题文字单独拿出来
            "text", "") for header in parse_draft_section_titles]

        relevant_contents = await subtopic_assistant.get_similar_written_contents_by_draft_section_titles(  # 正经注释：查找与草稿标题相关的已写内容，避免重复 / 大白话注释：看看之前有没有写过类似的内容，有的话可以参考
            current_subtopic_task, parse_draft_section_titles_text, self.global_written_sections
        )

        # Write subtopic report (images are pre-generated at the main research level)
        subtopic_report = await subtopic_assistant.write_report(  # 正经注释：生成子话题报告，传入已有标题和相关内容 / 大白话注释：让子研究员把报告写出来，注意别跟之前写过的重复
            existing_headers=self.existing_headers,  # 正经注释：传入已存在的标题列表 / 大白话注释：告诉它已经写了哪些标题
            relevant_written_contents=relevant_contents,  # 正经注释：传入相关的已写内容 / 大白话注释：给它看看之前写过的类似内容
        )

        self.global_written_sections.extend(self.gpt_researcher.extract_sections(subtopic_report))  # 正经注释：将新写的章节加入全局已写章节追踪 / 大白话注释：把新写的内容记到"已写记录"里
        self.global_context = list(set(self._hashable_context(subtopic_assistant.context)))  # 正经注释：用子话题研究的新上下文更新全局上下文（去重） / 大白话注释：把子研究员新发现的资料更新到公共知识库
        self.global_urls.update(subtopic_assistant.visited_urls)  # 正经注释：将子话题新访问的 URL 加入全局集合 / 大白话注释：把子研究员访问过的新网址记下来

        self.existing_headers.append({  # 正经注释：记录当前子话题的标题结构到已有标题列表 / 大白话注释：把这次写的标题也记下来
            "subtopic task": current_subtopic_task,  # 正经注释：子话题任务描述 / 大白话注释：哪个子话题
            "headers": self.gpt_researcher.extract_headers(subtopic_report),  # 正经注释：提取报告中的标题结构 / 大白话注释：写了哪些标题
        })

        return {"topic": subtopic, "report": subtopic_report}  # 正经注释：返回子话题信息和报告 / 大白话注释：把结果交出去

    async def _construct_detailed_report(self, introduction: str, report_body: str) -> str:
        """
        构建最终的详细报告

        【正经注释】
        将报告的各个组成部分（引言、目录、正文、结论）组合为最终的完整报告。
        步骤：生成目录 -> 撰写结论 -> 添加引用来源 -> 拼接所有部分。
        图片已在 conduct_research() 阶段预生成并在 write_report() 中嵌入。

        【大白话注释】
        把所有做好的零件拼成完整报告。具体是：
        根据正文生成一个目录 -> 写个总结 -> 给总结加上引用来源 ->
        然后按"引言 + 目录 + 正文 + 结论"的顺序拼在一起。
        图片在之前的步骤已经嵌入好了，不用再管。

        Args:
            introduction: 报告引言文本
            report_body: 所有子话题拼接后的正文文本
        Returns:
            str: 完整的详细报告文本
        """
        toc = self.gpt_researcher.table_of_contents(report_body)  # 正经注释：根据正文内容生成目录 / 大白话注释：根据正文自动生成一份目录
        conclusion = await self.gpt_researcher.write_report_conclusion(report_body)  # 正经注释：基于正文内容生成报告结论 / 大白话注释：写个漂亮的总结
        conclusion_with_references = self.gpt_researcher.add_references(  # 正经注释：在结论中添加参考来源链接 / 大白话注释：给总结加上引用的链接
            conclusion, self.gpt_researcher.visited_urls)
        report = f"{introduction}\n\n{toc}\n\n{report_body}\n\n{conclusion_with_references}"  # 正经注释：按顺序拼接所有部分组成最终报告 / 大白话注释：把开头、目录、正文、结尾拼在一起

        # Note: Images are now pre-generated during conduct_research() and embedded during write_report()
        return report  # 正经注释：返回完整的详细报告 / 大白话注释：把做好的完整报告交出去
