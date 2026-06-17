"""
【正经注释】
聊天代理模块，提供带记忆功能的对话式研究助手。
核心类 ChatAgentWithMemory 封装了基于研究报告上下文的交互式问答能力，
集成向量存储检索和 Tavily 联网搜索，支持通过 WebSocket 流式输出响应。
通过 LangChain 工具调用机制实现 LLM 自主决策是否需要联网搜索。

【大白话注释】
这个文件是聊天机器人的核心代码。
用户生成研究报告后，可以继续跟 AI 聊天，AI 会：
1. 根据报告内容回答问题（用向量搜索找相关段落）
2. 实在不行就上网搜一下（用 Tavily 搜索引擎）
3. 通过 WebSocket 把回答实时推送给前端
简单说就是：一个能看报告、能上网、能聊天的 AI 助手。
"""

import logging  # 正经注释：日志记录模块，用于输出运行时日志信息 / 大白话注释：打印日志用的，出了问题好排查
import os  # 正经注释：操作系统接口模块，用于读取环境变量等 / 大白话注释：跟操作系统打交道的，比如读环境变量里的 API Key
import uuid  # 正经注释：UUID 生成模块，用于生成唯一标识符 / 大白话注释：生成随机不重复 ID 的工具
import json  # 正经注释：JSON 序列化与反序列化模块 / 大白话注释：处理 JSON 数据的工具
from fastapi import WebSocket  # 正经注释：FastAPI 的 WebSocket 支持，用于实时双向通信 / 大白话注释：让服务器和浏览器能实时互发消息的管道
from typing import List, Dict, Any  # 正经注释：类型提示模块，提供类型标注支持 / 大白话注释：代码里标注变量类型的，让代码更清晰

from langchain_text_splitters import RecursiveCharacterTextSplitter  # 正经注释：LangChain 文本分割器，用于将长文本按递归字符策略切分为块 / 大白话注释：把长文章切成一小块一小块的工具，方便后续搜索
from langchain_community.vectorstores import InMemoryVectorStore  # 正经注释：LangChain 内存向量存储，用于在内存中存储和检索向量嵌入 / 大白话注释：在内存里存向量（一种数学表示）的仓库，用来做相似度搜索
from gpt_researcher.memory import Memory  # 正经注释：GPT Researcher 记忆模块，提供嵌入模型管理能力 / 大白话注释：把文字变成向量（数字）的工具
from gpt_researcher.config.config import Config  # 正经注释：GPT Researcher 配置管理类，统一管理所有配置项 / 大白话注释：读取配置文件的，比如用哪个模型、哪个搜索引擎
from gpt_researcher.utils.llm import create_chat_completion  # 正经注释：LLM 聊天补全工具函数，统一调用各 LLM 提供商 / 大白话注释：调用 AI 大模型生成回答的函数
from gpt_researcher.utils.tools import create_chat_completion_with_tools, create_search_tool  # 正经注释：带工具调用的聊天补全函数及搜索工具创建函数 / 大白话注释：让 AI 能"动手干活"的工具函数，比如自动触发搜索
from tavily import TavilyClient  # 正经注释：Tavily 搜索引擎客户端，用于执行联网搜索 / 大白话注释：上网搜东西的工具，Tavily 是一个专门给 AI 用的搜索引擎
from datetime import datetime  # 正经注释：日期时间模块，用于获取当前时间戳 / 大白话注释：获取当前日期和时间的

# 正经注释：初始化日志记录器实例，使用当前模块名作为日志名称 / 大白话注释：搞一个日志打印机，方便看程序跑到哪了
# Get logger instance
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()  # Only log to console  # 正经注释：仅将日志输出到控制台标准输出流 / 大白话注释：日志只打印到屏幕上，不写到文件里
    ]
)

# 正经注释：LLM 客户端现在通过 GPT Researcher 统一的 LLM 系统管理
# 支持 OpenAI、Google Gemini、Anthropic 等多种已配置的提供者
# Note: LLM client is now handled through GPT Researcher's unified LLM system
# This supports all configured providers (OpenAI, Google Gemini, Anthropic, etc.)

def get_tools():
    """定义 LLM 函数调用可用的工具列表（主要兼容 OpenAI 格式的提供者）。

    【正经注释】
    构建 OpenAI Function Calling 格式的工具定义列表，
    当前仅包含 quick_search 联网搜索工具，供 LLM 在对话中自主决定是否调用。

    【大白话注释】
    告诉 AI "你能用什么工具"。现在只有一个工具：quick_search（快速搜索）。
    AI 聊天的时候如果发现自己不知道的事，就会用这个工具去网上搜。

    Returns:
        list: 工具定义列表，符合 OpenAI Function Calling 规范
    """
    tools = [
        {
            "type": "function",  # 正经注释：工具类型为函数调用 / 大白话注释：告诉 AI 这是一个可调用的函数
            "function": {
                "name": "quick_search",  # 正经注释：工具名称为 quick_search / 大白话注释：工具的名字叫"快速搜索"
                "description": "Search for current events or online information when you need new knowledge that doesn't exist in the current context",
                "parameters": {  # 正经注释：工具参数定义，遵循 JSON Schema 规范 / 大白话注释：告诉 AI 调用这个工具需要传什么参数
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",  # 正经注释：查询关键词参数，类型为字符串 / 大白话注释：要搜什么内容，传个字符串就行
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]  # 正经注释：query 为必填参数 / 大白话注释：搜索关键词是必须填的，不然搜啥？
                }
            }
        }
    ]
    return tools  # 正经注释：返回工具定义列表 / 大白话注释：把工具列表交出去

class ChatAgentWithMemory:
    """带记忆功能的聊天代理类，基于研究报告上下文进行交互式问答。

    【正经注释】
    该类封装了基于研究报告的智能对话能力，核心特性包括：
    - 基于向量存储的文档检索（RAG 模式）
    - 集成 Tavily 搜索引擎的联网搜索能力
    - 通过 LangChain 工具调用机制实现 LLM 自主决策
    - 支持工具调用元数据的收集与传递

    【大白话注释】
    这个类是"能记住报告内容的聊天机器人"。它能做到：
    1. 记住你之前生成的研究报告内容
    2. 根据报告回答你的问题（用向量搜索找相关段落）
    3. 不够的话还能上网搜
    4. 把搜索结果和回答的来源信息告诉前端展示
    """

    def __init__(
        self,
        report: str,
        config_path="default",
        headers=None,
        vector_store=None
    ):
        """初始化聊天代理实例。

        【正经注释】
        构造函数接收研究报告文本、配置路径、请求头和可选的向量存储实例，
        初始化配置管理器、Tavily 搜索客户端等核心组件。

        【大白话注释】
        创建聊天机器人时要告诉它：
        - report: 研究报告的内容（机器人要"记住"的）
        - config_path: 配置文件路径（默认用默认配置）
        - headers: 请求头信息（一般用不上）
        - vector_store: 向量存储（如果外面已经有就不用重新建了）

        Args:
            report (str): 研究报告文本
            config_path (str): 配置文件路径，默认为 "default"
            headers: HTTP 请求头
            vector_store: 可选的外部向量存储实例
        """
        self.report = report  # 正经注释：存储研究报告全文 / 大白话注释：把报告内容存起来，聊天的时候要用
        self.headers = headers  # 正经注释：存储 HTTP 请求头信息 / 大白话注释：保存请求头，万一需要呢
        self.config = Config(config_path)  # 正经注释：初始化配置管理器实例 / 大白话注释：读取配置，知道用哪个 AI 模型
        self.vector_store = vector_store  # 正经注释：存储外部传入的向量存储实例 / 大白话注释：外面传进来的向量仓库，没有就后面自己建
        self.retriever = None  # 正经注释：检索器实例，初始为空 / 大白话注释：用来搜索报告内容的工具，先设为空
        self.search_metadata = None  # 正经注释：搜索元数据，记录最近一次搜索的结果信息 / 大白话注释：存最近一次搜索的结果信息（搜了啥、找到啥）

        # Initialize Tavily client (optional - only if API key is available)
        # 正经注释：初始化 Tavily 搜索客户端（可选，仅在 API Key 可用时启用）
        # 大白话注释：看看有没有配置 Tavily 搜索引擎的密钥，有的话就能联网搜索
        tavily_api_key = os.environ.get("TAVILY_API_KEY")  # 正经注释：从环境变量获取 Tavily API Key / 大白话注释：去环境变量里找 Tavily 的密钥
        if tavily_api_key:
            self.tavily_client = TavilyClient(api_key=tavily_api_key)  # 正经注释：创建 Tavily 客户端实例 / 大白话注释：密钥有了，创建搜索引擎客户端
        else:
            self.tavily_client = None  # 正经注释：无 API Key 时客户端设为空 / 大白话注释：没密钥就没法搜索，设为空
            logger.warning("TAVILY_API_KEY not set - web search in chat will be disabled")  # 正经注释：记录警告日志 / 大白话注释：打印个警告，告诉管理员没配搜索密钥

        # Process document and create vector store if not provided
        # 正经注释：若未提供外部向量存储，则处理文档并创建向量存储（当前被条件 False 禁用）
        # 大白话注释：如果没有现成的向量仓库，本来应该自己建一个，但现在这个功能被关掉了（and False）
        if not self.vector_store and False:
            self._setup_vector_store()  # 正经注释：调用内部方法初始化向量存储 / 大白话注释：自己建一个向量仓库（但现在不会执行）
    
    def _setup_vector_store(self):
        """初始化向量存储，用于文档检索。

        【正经注释】
        内部方法，将报告文本分割为块后生成向量嵌入，
        存储到内存向量库中，并创建基于相似度的检索器。

        【大白话注释】
        这个方法把报告切成小块，然后把每块变成一组数字（向量），
        存到内存里的向量仓库。以后问问题的时候，就能找到最相关的段落。
        """
        # Process document into chunks
        # 正经注释：将报告文档处理为适合嵌入的文本块 / 大白话注释：把报告切成一小块一小块
        documents = self._process_document(self.report)

        # Create unique thread ID
        # 正经注释：生成唯一的会话线程标识符 / 大白话注释：给这次对话生成一个唯一编号
        self.thread_id = str(uuid.uuid4())

        # Setup embeddings and vector store
        # 正经注释：初始化嵌入模型，基于配置中的嵌入提供者和模型 / 大白话注释：准备好把文字变成数字向量的工具
        cfg = Config()
        self.embedding = Memory(
            cfg.embedding_provider,  # 正经注释：嵌入提供者，如 OpenAI / 大白话注释：用哪家的模型来生成向量
            cfg.embedding_model,  # 正经注释：嵌入模型名称 / 大白话注释：具体用哪个模型
            **cfg.embedding_kwargs  # 正经注释：嵌入模型的额外参数 / 大白话注释：其他配置参数
        ).get_embeddings()

        # Create vector store and retriever
        # 正经注释：创建内存向量存储实例并添加文本块，配置检索器返回 Top-4 结果 / 大白话注释：建一个仓库把文本块存进去，设置搜索时返回最相关的4个结果
        self.vector_store = InMemoryVectorStore(self.embedding)  # 正经注释：基于嵌入模型创建内存向量存储 / 大白话注释：在内存里建个向量仓库
        self.vector_store.add_texts(documents)  # 正经注释：将文本块添加到向量存储中 / 大白话注释：把切好的文本块存进去
        self.retriever = self.vector_store.as_retriever(k=4)  # 正经注释：创建检索器，设置返回最相似的 4 个结果 / 大白话注释：设置搜索参数，每次找最相关的4块内容
        
    def _process_document(self, report):
        """将报告文本分割为适合嵌入的文本块。

        【正经注释】
        使用递归字符文本分割器，按指定块大小和重叠量
        将长文本切分为多个块，以平衡语义完整性和检索粒度。

        【大白话注释】
        把长报告切成小块。每块 1024 个字符，相邻块之间有 20 个字符重叠，
        这样切出来的块既不会太长也不会把一句话切成两半。

        Args:
            report (str): 待分割的报告文本

        Returns:
            list: 分割后的文本块列表
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024,  # 正经注释：每个文本块的最大字符数 / 大白话注释：每块最多1024个字符
            chunk_overlap=20,  # 正经注释：相邻文本块之间的重叠字符数 / 大白话注释：相邻块有20个字符重叠，防止关键信息被切断
            length_function=len,  # 正经注释：文本长度计算函数 / 大白话注释：用 len() 函数来计算文本长度
            is_separator_regex=False,  # 正经注释：分隔符不使用正则表达式 / 大白话注释：分隔符就按普通文本处理，不用正则
        )
        documents = text_splitter.split_text(report)  # 正经注释：执行文本分割操作 / 大白话注释：把报告切成小块
        return documents  # 正经注释：返回分割后的文本块列表 / 大白话注释：把切好的块交出去

    def quick_search(self, query):
        """使用 Tavily 搜索引擎执行联网搜索，获取当前信息。

        【正经注释】
        调用 Tavily API 执行 Web 搜索，返回搜索结果，
        同时将搜索元数据（来源、标题、摘要）存储到实例属性中供前端展示。

        【大白话注释】
        用 Tavily 搜索引擎上网搜东西。搜完之后把结果存起来，
        一份给 AI 看用来回答问题，一份给前端显示"我搜了这些来源"。

        Args:
            query (str): 搜索查询关键词

        Returns:
            dict: 搜索结果字典，包含 results 列表；失败时包含 error 信息
        """
        try:
            # Check if Tavily client is available
            # 正经注释：检查 Tavily 客户端是否已初始化 / 大白话注释：先看看能不能联网搜索
            if self.tavily_client is None:
                logger.warning(f"Tavily client not available, skipping web search for: {query}")  # 正经注释：记录警告日志 / 大白话注释：告诉日志，搜索功能不可用
                self.search_metadata = {
                    "query": query,  # 正经注释：记录原始搜索查询 / 大白话注释：搜的是什么
                    "sources": [],  # 正经注释：来源列表为空 / 大白话注释：没找到任何来源
                    "error": "Web search is disabled - TAVILY_API_KEY not configured"  # 正经注释：错误描述信息 / 大白话注释：告诉用户为啥搜不了
                }
                return {
                    "error": "Web search is disabled - TAVILY_API_KEY not configured",  # 正经注释：返回错误信息 / 大白话注释：返回错误提示
                    "results": []  # 正经注释：返回空结果列表 / 大白话注释：没有搜索结果
                }

            logger.info(f"Performing web search for: {query}")  # 正经注释：记录搜索操作日志 / 大白话注释：打印日志说"我要搜索了"
            results = self.tavily_client.search(query=query, max_results=5)  # 正经注释：调用 Tavily API 执行搜索，限制最多 5 条结果 / 大白话注释：上网搜，最多找5条结果

            # Store search metadata for frontend
            # 正经注释：将搜索结果元数据存储到实例属性中，供前端展示来源信息 / 大白话注释：把搜索结果整理一下存起来，给前端页面显示用
            self.search_metadata = {
                "query": query,  # 正经注释：搜索查询关键词 / 大白话注释：搜了什么
                "sources": [
                    {"title": result.get("title", ""),  # 正经注释：来源标题 / 大白话注释：搜索结果的标题
                     "url": result.get("url", ""),  # 正经注释：来源 URL / 大白话注释：搜索结果的网址链接
                     "content": result.get("content", "")[:200] + "..." if len(result.get("content", "")) > 200 else result.get("content", "")}  # 正经注释：内容摘要，截取前 200 字符 / 大白话注释：搜索结果的内容摘要，太长就截断加省略号
                    for result in results.get("results", [])  # 正经注释：遍历搜索结果列表 / 大白话注释：一条一条处理搜索结果
                ]
            }

            return results  # 正经注释：返回完整的 Tavily 搜索结果 / 大白话注释：把搜索结果交出去
        except Exception as e:
            logger.error(f"Error performing web search: {str(e)}", exc_info=True)  # 正经注释：记录异常日志，包含完整堆栈信息 / 大白话注释：出错了，把错误信息记下来
            return {
                "error": str(e),  # 正经注释：返回错误描述 / 大白话注释：告诉调用方出了什么错
                "results": []  # 正经注释：返回空结果列表 / 大白话注释：搜索失败，没有结果
            }


    async def process_chat_completion(self, messages: List[Dict[str, str]]):
        """使用配置的 LLM 提供者处理聊天补全，支持工具调用。

        【正经注释】
        异步方法，通过 LangChain 工具调用机制将搜索工具绑定到 LLM，
        处理模型响应和工具调用元数据，将内部工具名称映射为前端可识别的格式。

        【大白话注释】
        这是核心方法——把用户的消息发给 AI 大模型，同时告诉 AI "你可以搜索"。
        AI 回答后，把 AI 调用了什么工具、搜了什么内容整理好返回。

        Args:
            messages (List[Dict[str, str]]): 对话消息列表，包含 role 和 content

        Returns:
            tuple: (str: AI 响应文本, list: 工具调用元数据列表)
        """
        # Create a search tool using the utility function
        # 正经注释：使用工具函数创建搜索工具实例，绑定当前对象的 quick_search 方法 / 大白话注释：把"上网搜索"这个功能包装成 AI 能调用的工具
        search_tool = create_search_tool(self.quick_search)

        # Use the tool-enabled chat completion utility
        # 正经注释：调用支持工具的聊天补全工具函数，传入搜索工具和 LLM 配置 / 大白话注释：把消息和工具一起发给 AI，让 AI 自己决定要不要搜索
        response, tool_calls_metadata = await create_chat_completion_with_tools(
            messages=messages,  # 正经注释：对话消息列表 / 大白话注释：用户和 AI 的聊天记录
            tools=[search_tool],  # 正经注释：可用工具列表 / 大白话注释：告诉 AI 可以用搜索工具
            model=self.config.smart_llm_model,  # 正经注释：智能 LLM 模型名称 / 大白话注释：用哪个 AI 模型（通常是最强的那个）
            llm_provider=self.config.smart_llm_provider,  # 正经注释：LLM 提供者 / 大白话注释：AI 模型是哪家提供的
            llm_kwargs=self.config.llm_kwargs,  # 正经注释：LLM 额外参数 / 大白话注释：其他配置参数
        )

        # Process metadata to match the expected format for the chat system
        # 正经注释：将工具调用元数据转换为聊天系统期望的格式 / 大白话注释：把 AI 调用工具的信息整理成前端能看懂的格式
        processed_metadata = []
        for metadata in tool_calls_metadata:  # 正经注释：遍历所有工具调用元数据 / 大白话注释：一条一条看 AI 调了什么工具
            if metadata.get("tool") == "search_tool":  # 正经注释：筛选搜索工具调用记录 / 大白话注释：只关心搜索相关的调用
                # Extract query from args
                # 正经注释：从工具调用参数中提取搜索查询 / 大白话注释：看看 AI 搜了什么关键词
                query = metadata.get("args", {}).get("query", "")

                # Trigger search again to get metadata (the search was already executed by LangChain)
                # 正经注释：重新触发搜索以获取元数据（实际搜索已由 LangChain 执行，此处为获取搜索来源信息）
                # 大白话注释：再搜一次！因为 LangChain 已经搜过了但没存元数据，这里再搜一次是为了拿到来源信息给前端看
                if query:
                    self.quick_search(query)  # This populates self.search_metadata  # 正经注释：调用搜索方法填充 search_metadata 属性 / 大白话注释：搜一下，把搜索来源信息存起来

                processed_metadata.append({
                    "tool": "quick_search",  # 正经注释：映射为前端识别的工具名称 / 大白话注释：告诉前端"AI 用了搜索工具"
                    "query": query,  # 正经注释：搜索查询关键词 / 大白话注释：搜了什么
                    "search_metadata": self.search_metadata  # 正经注释：搜索结果元数据（来源信息） / 大白话注释：搜索结果的详细信息（标题、链接、摘要）
                })

        return response, processed_metadata  # 正经注释：返回 AI 响应和工具调用元数据 / 大白话注释：把 AI 的回答和搜索信息一起交出去


    async def chat(self, messages, websocket=None):
        """与配置的 LLM 提供者进行对话（支持 OpenAI、Google Gemini、Anthropic 等）。

        【正经注释】
        异步聊天方法，构建包含研究报告上下文的系统提示词，
        格式化对话历史，调用 LLM 生成响应，并返回响应文本与工具调用元数据。

        【大白话注释】
        这是聊天的主入口！流程是：
        1. 把研究报告的内容塞进系统提示词里，告诉 AI "你是研究助手"
        2. 把用户之前的聊天记录整理好
        3. 发给 AI 让它回答
        4. 把 AI 的回答和它用了什么工具返回去

        Args:
            messages: 对话消息列表，包含 role 和 content
            websocket: 可选的 WebSocket 连接，用于流式响应

        Returns:
            tuple: (str: AI 响应消息, list: 工具使用元数据)
        """
        try:

            # Format system prompt with the report context
            # 正经注释：构建包含研究报告上下文的系统提示词 / 大白话注释：告诉 AI "你是谁、你要干嘛、报告内容是什么"
            system_prompt = f"""
            You are GPT Researcher, an autonomous research agent created by an open source community at https://github.com/assafelovic/gpt-researcher, homepage: https://gptr.dev.
            To learn more about GPT Researcher you can suggest to check out: https://docs.gptr.dev.

            This is a chat about a research report that you created. Answer based on the given context and report.
            You must include citations to your answer based on the report.

            You may use the quick_search tool when the user asks about information that might require current data
            not found in the report, such as recent events, updated statistics, or news. If there's no report available,
            you can use the quick_search tool to find information online.

            You must respond in markdown format. You must make it readable with paragraphs, tables, etc when possible.
            Remember that you're answering in a chat not a report.

            Assume the current time is: {datetime.now()}.

            Report: {self.report}

            """  # 正经注释：系统提示词末尾嵌入完整报告文本和当前时间 / 大白话注释：把报告全文和当前时间都塞进去

            # Format message history for OpenAI input
            # 正经注释：格式化对话历史，适配 LLM 输入格式 / 大白话注释：把聊天记录整理成 AI 能看懂的格式
            formatted_messages = []

            # Add system message first
            # 正经注释：首先添加系统角色消息 / 大白话注释：先把系统提示词放第一个
            formatted_messages.append({
                "role": "system",  # 正经注释：角色为系统 / 大白话注释：告诉 AI 这是系统指令
                "content": system_prompt  # 正经注释：系统提示词内容 / 大白话注释：上面拼好的那一大段提示词
            })

            # Add user/assistant message history - filter out non-essential fields
            # 正经注释：添加用户/助手的历史消息，过滤掉非必要字段 / 大白话注释：把之前的聊天记录加进去，只保留角色和内容
            for msg in messages:
                if 'role' in msg and 'content' in msg:  # 正经注释：验证消息包含必要字段 / 大白话注释：检查消息格式对不对
                    formatted_messages.append({
                        "role": msg["role"],  # 正经注释：消息角色（user 或 assistant） / 大白话注释：是用户说的还是 AI 说的
                        "content": msg["content"]  # 正经注释：消息内容 / 大白话注释：具体说了什么
                    })
                else:
                    logger.warning(f"Skipping message with missing role or content: {msg}")  # 正经注释：记录跳过格式不完整的消息 / 大白话注释：消息格式不对，跳过它并打个警告

            # Process the chat using configured LLM provider
            # 正经注释：通过配置的 LLM 提供者处理聊天补全 / 大白话注释：把整理好的消息发给 AI，等它回答
            ai_message, tool_calls_metadata = await self.process_chat_completion(formatted_messages)

            # Provide fallback response if message is empty
            # 正经注释：若 AI 响应为空则提供兜底回复 / 大白话注释：如果 AI 啥也没说，就给个默认回答
            if not ai_message:
                logger.warning("No AI message content found in response, using fallback message")  # 正经注释：记录警告 / 大白话注释：打印日志说 AI 没回复
                ai_message = "I apologize, but I couldn't generate a proper response. Please try asking your question again."  # 正经注释：兜底回复文本 / 大白话注释：抱歉，我没能生成回复，请再试一次

            logger.info(f"Generated response: {ai_message[:100]}..." if len(ai_message) > 100 else f"Generated response: {ai_message}")  # 正经注释：记录生成的响应摘要 / 大白话注释：打印一下 AI 回答的前100个字符

            # Return both the message and any metadata about tools used
            # 正经注释：返回 AI 响应消息和工具调用元数据 / 大白话注释：把 AI 的回答和它用了什么工具一起返回
            return ai_message, tool_calls_metadata

        except Exception as e:
            logger.error(f"Error in chat: {str(e)}", exc_info=True)  # 正经注释：记录异常日志及完整堆栈 / 大白话注释：出错了，记下来
            raise  # 正经注释：重新抛出异常，由上层处理 / 大白话注释：把错误往上抛，让调用者知道出问题了

    def get_context(self):
        """返回当前聊天的上下文内容。

        【正经注释】
        获取当前聊天代理所持有的研究报告全文，作为上下文信息返回。

        【大白话注释】
        把存着的研究报告内容交出去，让外面的人知道 AI 在聊啥。

        Returns:
            str: 研究报告全文
        """
        return self.report  # 正经注释：返回存储的研究报告文本 / 大白话注释：把报告内容交出去
