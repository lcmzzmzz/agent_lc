"""
深度研究示例模块（deep_research/example）

【正经注释】
本模块实现了 DeepResearch 类和 ResearchProgress 数据类，提供完整的
递归式深度研究功能。核心流程为：生成追问明确方向 -> 生成搜索查询 ->
并发执行搜索与信息提取 -> 递归深入（广度逐层减半、深度逐层减一） ->
汇总所有发现 -> 生成带引用的综合报告。
支持并发限制、进度回调、引用追踪和 o3-mini 推理模型等特性。

【大白话注释】
这个文件是深度研究的"核心引擎"。它的工作方式就像剥洋葱：
先根据你的问题生成几个搜索词 -> 并发搜索 -> 提取关键发现和追问 ->
如果还没挖够深，就用追问生成新的搜索词继续挖 -> 一层比一层搜得更集中 ->
最后把所有发现汇总，生成一份带引用的详细报告。
o3-mini 推理模型负责"动脑子"的活，GPT-4o 负责"出苦力"的活。
"""

from typing import List, Dict, Any, Optional, Set  # 正经注释：导入类型提示工具 / 大白话注释：类型标注用的，告诉 Python 变量是啥类型
from fastapi import WebSocket  # 正经注释：导入 FastAPI 的 WebSocket 类 / 大白话注释：跟前端"打电话"用的
import asyncio  # 正经注释：异步编程核心库，用于并发控制和异步任务调度 / 大白话注释：异步用的，让多个搜索同时跑
import logging  # 正经注释：日志记录库 / 大白话注释：日志用的，出错了能查到原因
from gpt_researcher import GPTResearcher  # 正经注释：导入核心研究器类 / 大白话注释：把"研究大脑"请过来
from gpt_researcher.llm_provider.generic.base import ReasoningEfforts  # 正经注释：导入推理努力程度枚举 / 大白话注释：控制 AI 想多深的设置
from gpt_researcher.skills.deep_research import (  # 正经注释：导入深度研究技能的响应解析函数 / 大白话注释：导入几个解析工具，把 AI 返回的文本变成结构化数据
    parse_follow_up_questions_response,  # 正经注释：解析追问问题的响应 / 大白话注释：解析 AI 提出的追问
    parse_research_results_response,  # 正经注释：解析研究结果（发现+追问）的响应 / 大白话注释：解析搜到的结果
    parse_search_queries_response,  # 正经注释：解析搜索查询的响应 / 大白话注释：解析生成的搜索词
)
from gpt_researcher.utils.llm import create_chat_completion  # 正经注释：导入 LLM 调用工具函数 / 大白话注释：调用 AI 大模型的通用函数
from gpt_researcher.utils.enum import ReportType, ReportSource, Tone  # 正经注释：导入报告类型、数据来源和语气的枚举 / 大白话注释：导入几个常量定义

logger = logging.getLogger(__name__)  # 正经注释：创建当前模块的日志记录器 / 大白话注释：给自己建一个日志记录器

# Constants for models
GPT4_MODEL = "gpt-4o"  # For standard tasks  # 正经注释：GPT-4o 模型标识，用于一般性任务 / 大白话注释：普通活儿用这个模型
O3_MINI_MODEL = "o3-mini"  # For reasoning tasks  # 正经注释：o3-mini 推理模型，用于需要深度推理的任务 / 大白话注释：需要动脑子的活儿用这个推理模型
LLM_PROVIDER = "openai"  # 正经注释：LLM 供应商标识 / 大白话注释：用 OpenAI 的 API

class ResearchProgress:
    """
    研究进度追踪类

    【正经注释】
    用于跟踪和报告深度研究的执行进度，包括当前深度/广度层级、
    正在处理的查询、总查询数和已完成查询数。
    通过 on_progress 回调传递给调用方以实现实时进度展示。

    【大白话注释】
    这就是研究进度的"记分牌"。它记录着：现在挖到第几层了、这一层搜几个问题、
    已经搜了几个问题、当前在搜啥。每次有变化就通知外面的人。
    """
    def __init__(self, total_depth: int, total_breadth: int):  # 正经注释：初始化进度追踪器 / 大白话注释：建好记分牌
        self.current_depth = total_depth  # 正经注释：当前深度层级（初始等于总深度，递减） / 大白话注释：现在挖到第几层
        self.total_depth = total_depth  # 正经注释：总深度层级 / 大白话注释：总共要挖几层
        self.current_breadth = total_breadth  # 正经注释：当前广度（每层搜索的查询数） / 大白话注释：这一层要搜几个问题
        self.total_breadth = total_breadth  # 正经注释：总广度 / 大白话注释：总共要搜几个问题
        self.current_query: Optional[str] = None  # 正经注释：当前正在处理的查询字符串 / 大白话注释：现在正在搜啥
        self.total_queries = 0  # 正经注释：总查询数量 / 大白话注释：总共要搜多少次
        self.completed_queries = 0  # 正经注释：已完成查询数量 / 大白话注释：已经搜完了多少次

class DeepResearch:
    """
    深度研究核心类

    【正经注释】
    实现递归式深度研究流程。通过多轮搜索、信息提取和追问，
    逐层深入探索研究主题。每层广度减半、深度减一，直到达到设定的最深层次。
    最终汇总所有发现，生成包含引用来源的综合性研究报告。

    【大白话注释】
    这个类就是深度研究的"总指挥"。它的工作方式是：
    1. 先让 AI 提几个追问，搞清楚你到底想知道啥
    2. 根据问题生成一堆搜索词
    3. 同时搜索好几个词（有并发限制）
    4. 从搜索结果里提取关键发现
    5. 如果还没挖够深，就用追问当新搜索词继续挖（递归）
    6. 最后把所有发现拼在一起，写成一份带引用的大报告

    Attributes:
        query: 研究主题
        breadth: 每层搜索的查询数量
        depth: 递归深度（层数）
        concurrency_limit: 并发搜索的限制数
    """
    def __init__(
        self,
        query: str,  # 正经注释：用户的原始查询字符串 / 大白话注释：你想研究啥
        breadth: int = 4,  # 正经注释：每层搜索的查询数量，默认为 4 / 大白话注释：每一层搜几个关键词，默认 4 个
        depth: int = 2,  # 正经注释：递归深度，默认为 2 层 / 大白话注释：挖几层，默认挖 2 层
        websocket: Optional[WebSocket] = None,  # 正经注释：WebSocket 连接，可选 / 大白话注释：跟前端通话的"电话线"，可选
        tone: Tone = Tone.Objective,  # 正经注释：报告语气，默认为客观 / 大白话注释：用啥语气写，默认客观
        config_path: Optional[str] = None,  # 正经注释：配置文件路径，可选 / 大白话注释：配置文件在哪，可选
        headers: Optional[Dict] = None,  # 正经注释：自定义 HTTP 请求头，可选 / 大白话注释：额外的请求头，可选
        concurrency_limit: int = 2  # Match TypeScript version  # 正经注释：并发搜索数量限制，默认 2（与 TypeScript 版本一致） / 大白话注释：最多同时搜几个，默认 2 个，别太猛了
    ):
        self.query = query  # 正经注释：保存查询字符串 / 大白话注释：记住要研究啥
        self.breadth = breadth  # 正经注释：保存广度参数 / 大白话注释：记住每层搜几个
        self.depth = depth  # 正经注释：保存深度参数 / 大白话注释：记住挖几层
        self.websocket = websocket  # 正经注释：保存 WebSocket / 大白话注释：记住"电话线"
        self.tone = tone  # 正经注释：保存语气设置 / 大白话注释：记住语气
        self.config_path = config_path  # 正经注释：保存配置路径 / 大白话注释：记住配置文件位置
        self.headers = headers or {}  # 正经注释：保存请求头 / 大白话注释：记住请求头
        self.visited_urls: Set[str] = set()  # 正经注释：已访问 URL 集合 / 大白话注释：已经访问过的网址
        self.learnings: List[str] = []  # 正经注释：已收集的研究发现列表 / 大白话注释：已经搜到的重要发现
        self.concurrency_limit = concurrency_limit  # 正经注释：保存并发限制 / 大白话注释：记住最多同时搜几个

    async def generate_feedback(self, query: str, num_questions: int = 3) -> List[str]:
        """
        生成追问以明确研究方向

        【正经注释】
        使用 o3-mini 推理模型生成追问列表，帮助明确研究的具体方向。
        模型会根据原始查询判断是否需要追问，如果查询已经足够清晰，
        可能返回少于 num_questions 的问题。返回纯 JSON 格式。

        【大白话注释】
        让 AI 根据你的问题提几个追问，搞清楚你到底想知道啥。
        比如你问"怎么投资"，AI 可能会追问"你想投多少？""长期还是短期？""能承受多少风险？"。
        用的 o3-mini 推理模型，想得更深入。

        Args:
            query: 用户的原始查询
            num_questions: 最大追问数量，默认 3
        Returns:
            List[str]: 追问字符串列表
        """
        """Generate follow-up questions to clarify research direction"""
        messages = [  # 正经注释：构建 LLM 对话消息列表 / 大白话注释：给 AI 的"剧本"
            {
                "role": "system",  # 正经注释：系统角色消息，定义 AI 的行为 / 大白话注释：告诉 AI 它是谁、该怎么干
                "content": (
                    "You are an expert researcher helping to clarify research directions. "
                    "Return valid JSON only."
                ),
            },
            {
                "role": "user",  # 正经注释：用户角色消息，包含具体的追问请求 / 大白话注释：具体的任务描述
                "content": (
                    f"Given the following query from the user, ask some follow up questions to clarify the research direction. "
                    f"Return a maximum of {num_questions} questions, but feel free to return less if the original query is clear.\n\n"
                    'Return ONLY a JSON object using this exact schema:\n{"questions": ["<question 1>", "<question 2>"]}\n\n'
                    f"Query: {query}"
                ),
            },
        ]

        response = await create_chat_completion(  # 正经注释：调用 LLM 生成追问 / 大白话注释：让 AI 动脑子想几个追问
            messages=messages,  # 正经注释：传入消息列表 / 大白话注释：把剧本给它
            llm_provider=LLM_PROVIDER,  # 正经注释：指定 LLM 供应商 / 大白话注释：用 OpenAI
            model=O3_MINI_MODEL,  # Using reasoning model for better question generation  # 正经注释：使用 o3-mini 推理模型 / 大白话注释：用推理模型，想得更深
            temperature=0.7,  # 正经注释：温度参数 0.7，平衡创造性和一致性 / 大白话注释：稍微有点创造力，但不会太离谱
            max_tokens=500,  # 正经注释：最大生成 token 数 / 大白话注释：别写太长
            reasoning_effort=ReasoningEfforts.High.value  # 正经注释：使用高推理努力程度 / 大白话注释：使劲想，想仔细点
        )

        return parse_follow_up_questions_response(response, num_questions)  # 正经注释：解析 AI 返回的追问 JSON / 大白话注释：把 AI 的回答解析成问题列表

    async def generate_serp_queries(self, query: str, num_queries: int = 3) -> List[Dict[str, str]]:
        """
        生成搜索查询

        【正经注释】
        使用 GPT-4o 模型根据研究主题生成多个搜索查询，每个查询附带一个研究目标。
        返回格式为 [{"query": "搜索词", "researchGoal": "研究目标"}] 的结构化数据。
        用于指导后续的并发搜索。

        【大白话注释】
        让 AI 根据你的问题想出几个搜索关键词，每个关键词还带上"我想通过这次搜索找到什么"。
        比如研究"怎么投资"，可能生成"新手投资入门指南"、"低风险投资方式"等搜索词。

        Args:
            query: 研究主题
            num_queries: 需要生成的查询数量，默认 3
        Returns:
            List[Dict[str, str]]: 搜索查询列表，每项包含 query 和 researchGoal
        """
        """Generate SERP queries for research"""
        messages = [  # 正经注释：构建 LLM 对话消息 / 大白话注释：给 AI 的"剧本"
            {
                "role": "system",  # 正经注释：系统角色消息 / 大白话注释：告诉 AI 怎么干
                "content": (
                    "You are an expert researcher generating search queries. "
                    "Return valid JSON only. Do not include markdown, code fences, bullets, numbering, or prose."
                ),
            },
            {
                "role": "user",  # 正经注释：用户角色消息 / 大白话注释：具体的任务
                "content": (
                    f"Given the following prompt, generate {num_queries} unique search queries to research the topic thoroughly. "
                    "For each query, provide a research goal.\n\n"
                    'Return ONLY a JSON array of objects using this exact schema:\n'
                    '[{"query": "<search query>", "researchGoal": "<research goal>"}]\n\n'
                    f"Prompt: {query}"
                ),
            },
        ]

        response = await create_chat_completion(  # 正经注释：调用 LLM 生成搜索查询 / 大白话注释：让 AI 想搜索词
            messages=messages,  # 正经注释：传入消息 / 大白话注释：把剧本给它
            llm_provider=LLM_PROVIDER,  # 正经注释：指定供应商 / 大白话注释：用 OpenAI
            model=GPT4_MODEL,  # Using GPT-4 for general task  # 正经注释：使用 GPT-4o 处理一般性任务 / 大白话注释：用 GPT-4o，这个活不需要深度推理
            temperature=0.7,  # 正经注释：温度参数 / 大白话注释：稍微有点创造力
            max_tokens=1000  # 正经注释：最大 token 数 / 大白话注释：可以写长一点
        )

        return parse_search_queries_response(response, num_queries)  # 正经注释：解析 AI 返回的搜索查询 JSON / 大白话注释：把 AI 的回答解析成搜索词列表

    async def process_serp_result(self, query: str, context: str, num_learnings: int = 3) -> Dict[str, List[str]]:
        """
        处理搜索结果以提取研究发现和追问

        【正经注释】
        使用 o3-mini 推理模型分析搜索结果，提取关键研究发现（insight）和后续追问。
        每个发现附带来源 URL 引用。返回结构化的 JSON 数据，包含 learnings 和
        followUpQuestions 两个字段。

        【大白话注释】
        把搜到的结果交给 AI 分析，让它从中提取出"最重要的发现"和"还有什么值得继续挖的"。
        每个发现都会标注来源网址。这就是"从大海里捞珍珠"的步骤。

        Args:
            query: 原始搜索查询
            context: 搜索结果文本
            num_learnings: 最大提取发现数量，默认 3
        Returns:
            Dict: 包含 learnings（发现列表）和 followUpQuestions（追问列表）的字典
        """
        """Process research results to extract learnings and follow-up questions"""
        messages = [  # 正经注释：构建 LLM 对话消息 / 大白话注释：给 AI 的"剧本"
            {
                "role": "system",  # 正经注释：系统角色消息 / 大白话注释：告诉 AI 怎么干
                "content": (
                    "You are an expert researcher analyzing search results. "
                    "Return valid JSON only."
                ),
            },
            {
                "role": "user",  # 正经注释：用户角色消息，包含搜索结果和分析要求 / 大白话注释：具体的分析任务和搜索结果
                "content": (
                    f"Given the following research results for the query '{query}', extract key learnings and suggest "
                    "follow-up questions. For each learning, include a citation to the source URL if available.\n\n"
                    'Return ONLY a JSON object using this exact schema:\n'
                    '{"learnings": [{"insight": "<insight>", "sourceUrl": "<url or empty string>"}], '
                    '"followUpQuestions": ["<question 1>", "<question 2>"]}\n\n'
                    f"Research results:\n{context}"
                ),
            },
        ]

        response = await create_chat_completion(  # 正经注释：调用 LLM 分析搜索结果 / 大白话注释：让 AI 从搜到的内容里提炼精华
            messages=messages,  # 正经注释：传入消息 / 大白话注释：把剧本和搜索结果给它
            llm_provider=LLM_PROVIDER,  # 正经注释：指定供应商 / 大白话注释：用 OpenAI
            model=O3_MINI_MODEL,  # Using reasoning model for analysis  # 正经注释：使用 o3-mini 推理模型进行分析 / 大白话注释：用推理模型，分析得更透彻
            temperature=0.7,  # 正经注释：温度参数 / 大白话注释：稍微有点创造力
            max_tokens=1000,  # 正经注释：最大 token 数 / 大白话注释：可以写长一点
            reasoning_effort=ReasoningEfforts.High.value  # 正经注释：高推理努力 / 大白话注释：使劲想
        )

        return parse_research_results_response(response, num_learnings)  # 正经注释：解析 AI 返回的研究结果 JSON / 大白话注释：把 AI 的分析结果解析出来

    async def deep_research(
        self,
        query: str,  # 正经注释：当前层的研究查询 / 大白话注释：这层要研究啥
        breadth: int,  # 正经注释：当前层的搜索查询数量 / 大白话注释：这层搜几个关键词
        depth: int,  # 正经注释：剩余递归深度 / 大白话注释：还能挖几层
        learnings: List[str] = None,  # 正经注释：已收集的研究发现 / 大白话注释：之前已经搜到的东西
        citations: Dict[str, str] = None,  # 正经注释：已收集的引用来源 / 大白话注释：之前记下的引用链接
        visited_urls: Set[str] = None,  # 正经注释：已访问的 URL 集合 / 大白话注释：之前访问过的网址
        on_progress = None  # 正经注释：进度回调函数 / 大白话注释：研究进度通知函数
    ) -> Dict[str, Any]:
        """
        执行递归深度研究

        【正经注释】
        核心递归方法。在每一层：生成搜索查询 -> 并发执行搜索 -> 提取研究发现 ->
        如果 depth > 1 则递归深入（广度减半、深度减一）。使用信号量控制并发数，
        避免过多并发请求。所有层级的发现、引用和 URL 在递归过程中持续累积。

        【大白话注释】
        这是深度研究的"核心引擎"，像剥洋葱一样一层层深入。
        每一层的流程：先想几个搜索词 -> 同时搜索 -> 提取重要发现 ->
        如果还没到底，就用追问当新搜索词，继续往下挖。
        每一层搜索的关键词比上一层少一半（更集中），深度减一。
        所有搜到的东西都攒着，一层一层往下传。

        Args:
            query: 研究查询
            breadth: 搜索广度
            depth: 剩余递归深度
            learnings: 已收集发现
            citations: 已收集引用
            visited_urls: 已访问 URL
            on_progress: 进度回调
        Returns:
            Dict: 包含 learnings、visited_urls 和 citations 的结果字典
        """
        """Conduct deep iterative research"""
        if learnings is None:  # 正经注释：初始化发现列表 / 大白话注释：如果没传之前的发现，就从头开始
            learnings = []
        if citations is None:  # 正经注释：初始化引用字典 / 大白话注释：如果没传之前的引用，就从头开始
            citations = {}
        if visited_urls is None:  # 正经注释：初始化已访问 URL 集合 / 大白话注释：如果没传之前的网址，就从头开始
            visited_urls = set()

        progress = ResearchProgress(depth, breadth)  # 正经注释：创建当前层的进度追踪对象 / 大白话注释：建好这层的"记分牌"

        if on_progress:  # 正经注释：如果有进度回调则通知 / 大白话注释：通知外面的人进度更新了
            on_progress(progress)

        # Generate search queries
        serp_queries = await self.generate_serp_queries(query, num_queries=breadth)  # 正经注释：生成当前层的搜索查询 / 大白话注释：让 AI 想出这层要搜的关键词
        progress.total_queries = len(serp_queries)  # 正经注释：记录总查询数 / 大白话注释：记下总共要搜几次

        all_learnings = learnings.copy()  # 正经注释：复制已有的发现列表 / 大白话注释：把之前搜到的东西复制一份
        all_citations = citations.copy()  # 正经注释：复制已有的引用字典 / 大白话注释：把之前的引用复制一份
        all_visited_urls = visited_urls.copy()  # 正经注释：复制已访问 URL 集合 / 大白话注释：把之前访问过的网址复制一份

        # Process queries with concurrency limit
        semaphore = asyncio.Semaphore(self.concurrency_limit)  # 正经注释：创建并发信号量，限制同时运行的搜索数量 / 大白话注释：设置"大门"，最多同时放几个任务进去

        async def process_query(serp_query: Dict[str, str]) -> Optional[Dict[str, Any]]:
            """
            处理单个搜索查询

            【正经注释】
            在信号量控制下执行单个查询的完整流程：创建研究器 -> 执行研究 ->
            提取上下文 -> 分析结果 -> 更新进度。异常时返回 None。

            【大白话注释】
            处理一个搜索词的完整流程：拿到搜索词 -> 排队进"大门" ->
            创建研究器 -> 搜索资料 -> 分析结果 -> 更新进度 -> 交差。
            如果出错了就返回空，不影响其他搜索。

            Args:
                serp_query: 搜索查询字典，包含 query 和 researchGoal
            Returns:
                结果字典或 None（出错时）
            """
            async with semaphore:  # 正经注释：获取信号量，控制并发数 / 大白话注释：排队等"大门"打开
                try:
                    progress.current_query = serp_query['query']  # 正经注释：更新当前处理的查询 / 大白话注释：记分牌上写"正在搜xxx"
                    if on_progress:  # 正经注释：通知进度更新 / 大白话注释：告诉外面"我在搜这个了"
                        on_progress(progress)

                    # Initialize researcher for this query
                    researcher = GPTResearcher(  # 正经注释：为当前查询创建独立的研究器 / 大白话注释：给这个搜索词派一个"研究员"
                        query=serp_query['query'],  # 正经注释：设置搜索查询 / 大白话注释：告诉研究员搜什么
                        report_type=ReportType.ResearchReport.value,  # 正经注释：使用标准研究报告类型 / 大白话注释：用标准研究模式
                        report_source=ReportSource.Web.value,  # 正经注释：使用 Web 数据源 / 大白话注释：从网上搜
                        tone=self.tone,  # 正经注释：继承语气设置 / 大白话注释：继承语气
                        websocket=self.websocket,  # 正经注释：继承 WebSocket / 大白话注释：接上"电话线"
                        config_path=self.config_path,  # 正经注释：继承配置 / 大白话注释：继承配置
                        headers=self.headers  # 正经注释：继承请求头 / 大白话注释：继承请求头
                    )

                    # Conduct research
                    await researcher.conduct_research()  # 正经注释：执行研究 / 大白话注释：让研究员去搜资料

                    # Get results
                    context = researcher.context  # 正经注释：获取研究上下文 / 大白话注释：拿到搜到的资料
                    visited = set(researcher.visited_urls)  # 正经注释：获取已访问的 URL / 大白话注释：拿到访问过的网址

                    # Process results
                    results = await self.process_serp_result(  # 正经注释：分析搜索结果，提取发现和追问 / 大白话注释：让 AI 从搜到的资料里提炼精华
                        query=serp_query['query'],  # 正经注释：传入查询 / 大白话注释：告诉 AI 搜的是什么
                        context=context  # 正经注释：传入搜索结果 / 大白话注释：把搜到的资料给它
                    )

                    # Update progress
                    progress.completed_queries += 1  # 正经注释：增加已完成查询计数 / 大白话注释：记分牌上"已搜完"+1
                    if on_progress:  # 正经注释：通知进度 / 大白话注释：告诉外面"又搜完一个了"
                        on_progress(progress)

                    return {  # 正经注释：返回查询结果 / 大白话注释：把搜到的结果打包交差
                        'learnings': results['learnings'],  # 正经注释：提取的研究发现 / 大白话注释：搜到的重要发现
                        'visited_urls': visited,  # 正经注释：访问过的 URL / 大白话注释：访问过的网址
                        'followUpQuestions': results['followUpQuestions'],  # 正经注释：后续追问 / 大白话注释：还有什么值得继续挖的
                        'researchGoal': serp_query['researchGoal'],  # 正经注释：本次搜索的研究目标 / 大白话注释：这次搜索想找到啥
                        'citations': results['citations']  # 正经注释：引用来源 / 大白话注释：引用的链接
                    }

                except Exception as e:  # 正经注释：捕获异常，记录错误日志 / 大白话注释：出错了别崩，记下来就行
                    logger.error(f"Error processing query '{serp_query['query']}': {str(e)}")
                    return None  # 正经注释：出错时返回 None / 大白话注释：出错了就返回空，别影响其他搜索

        # Process queries concurrently with limit
        tasks = [process_query(query) for query in serp_queries]  # 正经注释：为每个搜索查询创建并发任务 / 大白话注释：给每个搜索词都派一个任务
        results = await asyncio.gather(*tasks)  # 正经注释：并发执行所有任务 / 大白话注释：所有任务同时跑，等全部完成
        results = [r for r in results if r is not None]  # Filter out failed queries  # 正经注释：过滤掉失败的查询结果 / 大白话注释：把出错的空结果踢掉

        # Collect all results
        for result in results:  # 正经注释：遍历所有成功的搜索结果 / 大白话注释：一个一个看搜到了啥
            all_learnings.extend(result['learnings'])  # 正经注释：累积研究发现 / 大白话注释：把发现都攒起来
            all_visited_urls.update(set(result['visited_urls']))  # 正经注释：累积已访问 URL / 大白话注释：把网址都记下来
            all_citations.update(result['citations'])  # 正经注释：累积引用来源 / 大白话注释：把引用都记下来

            # Continue deeper if needed
            if depth > 1:  # 正经注释：如果还有剩余深度，递归深入 / 大白话注释：还没到底？继续挖！
                new_breadth = max(2, breadth // 2)  # 正经注释：新一层广度减半，最少 2 个 / 大白话注释：下一层搜少一点（减半），但最少也搜 2 个
                new_depth = depth - 1  # 正经注释：深度减一 / 大白话注释：还能再挖的层数减一

                # Create next query from research goal and follow-up questions
                next_query = f"""  # 正经注释：基于研究目标和追问构建下一层的查询 / 大白话注释：把"这轮想找啥"和"还有什么值得挖的"拼成下一轮的搜索指令
                Previous research goal: {result['researchGoal']}
                Follow-up questions: {' '.join(result['followUpQuestions'])}
                """

                # Recursive research
                deeper_results = await self.deep_research(  # 正经注释：递归调用自身进行更深层的研究 / 大白话注释：自己调用自己，再挖一层！
                    query=next_query,  # 正经注释：传入下一层的查询 / 大白话注释：用新的搜索指令
                    breadth=new_breadth,  # 正经注释：传入缩减后的广度 / 大白话注释：搜少一点
                    depth=new_depth,  # 正经注释：传入减一后的深度 / 大白话注释：少挖一层
                    learnings=all_learnings,  # 正经注释：传入已累积的发现 / 大白话注释：把之前搜到的都带上
                    citations=all_citations,  # 正经注释：传入已累积的引用 / 大白话注释：把引用也带上
                    visited_urls=all_visited_urls,  # 正经注释：传入已访问的 URL / 大白话注释：把网址也带上
                    on_progress=on_progress  # 正经注释：传入进度回调 / 大白话注释：进度通知也带上
                )

                all_learnings = deeper_results['learnings']  # 正经注释：更新为递归返回的发现 / 大白话注释：把更深层搜到的发现收下
                all_visited_urls = set(deeper_results['visited_urls'])  # 正经注释：更新为递归返回的 URL / 大白话注释：把更深层的网址也收下
                all_citations.update(deeper_results['citations'])  # 正经注释：合并递归返回的引用 / 大白话注释：把更深层的引用也合并进来

        return {  # 正经注释：返回当前层（及所有子层）的汇总结果 / 大白话注释：把这一层（和更深层）搜到的东西打包交出去
            'learnings': list(set(all_learnings)),  # 正经注释：去重后的发现列表 / 大白话注释：把重复的发现去掉
            'visited_urls': list(all_visited_urls),  # 正经注释：所有访问过的 URL / 大白话注释：所有访问过的网址
            'citations': all_citations  # 正经注释：所有引用来源 / 大白话注释：所有引用的链接
        }

    async def run(self, on_progress=None) -> str:
        """
        运行完整的深度研究流程并生成最终报告

        【正经注释】
        执行以下步骤：
        1. 生成追问以明确研究方向（自动回答以继续）
        2. 将原始查询与追问回答组合为增强查询
        3. 执行递归深度研究
        4. 使用研究发现作为上下文生成最终报告

        【大白话注释】
        深度研究的"一键启动"按钮。流程是：
        先让 AI 提几个追问 -> 自动回答"继续研究" ->
        把原始问题和追问拼在一起 -> 开始一层层深入搜索 ->
        把所有搜到的精华拼成上下文 -> 让 AI 写出最终报告。

        Args:
            on_progress: 进度回调函数，可选
        Returns:
            str: 最终的研究报告文本
        """
        """Run the deep research process and generate final report"""
        # Get initial feedback
        follow_up_questions = await self.generate_feedback(self.query)  # 正经注释：生成追问列表 / 大白话注释：让 AI 提几个追问

        # Collect answers (this would normally come from user interaction)
        answers = ["Automatically proceeding with research"] * len(follow_up_questions)  # 正经注释：自动生成回答，跳过用户交互 / 大白话注释：自动回答"继续研究"，不等真人回答

        # Combine query and Q&A
        combined_query = f"""  # 正经注释：将原始查询与问答对组合为增强查询 / 大白话注释：把问题和追问拼在一起，让搜索更有针对性
        Initial Query: {self.query}
        Follow-up Questions and Answers:
        {' '.join([f'Q: {q}\nA: {a}' for q, a in zip(follow_up_questions, answers)])}
        """

        # Run deep research
        results = await self.deep_research(  # 正经注释：执行递归深度研究 / 大白话注释：开始一层层深入挖掘
            query=combined_query,  # 正经注释：传入增强后的查询 / 大白话注释：用组合好的问题
            breadth=self.breadth,  # 正经注释：传入初始广度 / 大白话注释：每层搜几个
            depth=self.depth,  # 正经注释：传入初始深度 / 大白话注释：挖几层
            on_progress=on_progress  # 正经注释：传入进度回调 / 大白话注释：进度通知
        )

        # Generate final report
        researcher = GPTResearcher(  # 正经注释：创建用于生成最终报告的研究器实例 / 大白话注释：创建一个"写报告专员"
            query=self.query,  # 正经注释：使用原始查询 / 大白话注释：用最初的问题
            report_type=ReportType.DetailedReport.value,  # 正经注释：使用详细报告类型 / 大白话注释：写详细版报告
            report_source=ReportSource.Web.value,  # 正经注释：使用 Web 数据源 / 大白话注释：资料来自网上
            tone=self.tone,  # 正经注释：继承语气设置 / 大白话注释：用指定的语气
            websocket=self.websocket,  # 正经注释：继承 WebSocket / 大白话注释：接上"电话线"
            config_path=self.config_path,  # 正经注释：继承配置 / 大白话注释：继承配置
            headers=self.headers  # 正经注释：继承请求头 / 大白话注释：继承请求头
        )

        # Prepare context with citations
        context_with_citations = []  # 正经注释：准备带引用的上下文列表 / 大白话注释：把发现和引用拼在一起
        for learning in results['learnings']:  # 正经注释：遍历每个研究发现 / 大白话注释：一个一个看搜到了什么
            citation = results['citations'].get(learning, '')  # 正经注释：获取该发现对应的引用来源 / 大白话注释：看看这个发现引用的是哪个链接
            if citation:  # 正经注释：如果有引用来源则附加 / 大白话注释：有链接就加上
                context_with_citations.append(f"{learning} [Source: {citation}]")
            else:  # 正经注释：没有引用来源则直接使用 / 大白话注释：没链接就光写发现
                context_with_citations.append(learning)

        # Set enhanced context for final report
        researcher.context = "\n".join(context_with_citations)  # 正经注释：将带引用的上下文设置为研究器的上下文 / 大白话注释：把所有发现拼成一段文字给写报告专员
        researcher.visited_urls = set(results['visited_urls'])  # 正经注释：设置所有访问过的 URL / 大白话注释：把访问过的网址也给它

        # Generate report
        report = await researcher.write_report()  # 正经注释：生成最终报告 / 大白话注释：让专员把报告写出来
        return report  # 正经注释：返回报告文本 / 大白话注释：把报告交出去
