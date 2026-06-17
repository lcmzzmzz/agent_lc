"""通用大语言模型（LLM）提供者基类。        # 正经注释：通用LLM提供者模块，封装多种大语言模型的统一调用接口 / 大白话注释：这是个万能翻译官，不管你用的是OpenAI还是Anthropic还是别的啥模型，都能通过它来统一调用"""
# 正经注释：以下是标准库和第三方库的导入 / 大白话注释：导入各种工具包
import aiofiles                                                                # 正经注释：异步文件操作库 / 大白话注释：用来异步读写文件的库
import asyncio                                                                 # 正经注释：异步编程核心库 / 大白话注释：Python异步编程的基础库
import importlib                                                               # 正经注释：动态导入模块的工具 / 大白话注释：运行时动态加载Python包的工具
import json                                                                    # 正经注释：JSON序列化/反序列化库 / 大白话注释：处理JSON数据的库
import subprocess                                                              # 正经注释：子进程管理库 / 大白话注释：用来在代码里执行系统命令的库
import sys                                                                     # 正经注释：系统相关参数和函数 / 大白话注释：获取Python解释器信息的库
import traceback                                                               # 正经注释：堆栈跟踪工具 / 大白话注释：用来打印错误调用栈的库
from typing import Any                                                         # 正经注释：类型注解中的任意类型 / 大白话注释：类型提示用的，表示啥类型都行
from colorama import Fore, Style, init                                         # 正经注释：终端彩色输出库 / 大白话注释：让终端打印的东西带颜色的库
import os                                                                      # 正经注释：操作系统接口 / 大白话注释：跟操作系统打交道的库
from enum import Enum                                                          # 正经注释：枚举类型基类 / 大白话注释：用来定义常量集合的库

_SUPPORTED_PROVIDERS = {                                                       # 正经注释：支持的LLM提供者名称集合 / 大白话注释：所有支持的AI模型供应商名单
    "openai",                                                                  # 正经注释：OpenAI（GPT系列） / 大白话注释：ChatGPT那个公司
    "anthropic",                                                               # 正经注释：Anthropic（Claude系列） / 大白话注释：Claude那个公司
    "azure_openai",                                                            # 正经注释：Azure托管的OpenAI服务 / 大白话注释：微软云上的OpenAI
    "cohere",                                                                  # 正经注释：Cohere语言模型平台 / 大白话注释：另一个AI模型平台
    "google_vertexai",                                                         # 正经注释：Google Vertex AI平台 / 大白话注释：谷歌云上的AI服务
    "google_genai",                                                            # 正经注释：Google Generative AI（Gemini） / 大白话注释：谷歌的Gemini模型
    "fireworks",                                                               # 正经注释：Fireworks AI推理平台 / 大白话注释：一个快速跑模型的平台
    "ollama",                                                                  # 正经注释：Ollama本地模型运行工具 / 大白话注释：在自己电脑上跑AI模型的工具
    "together",                                                                # 正经注释：Together AI推理平台 / 大白话注释：又一个跑模型的云平台
    "mistralai",                                                               # 正经注释：Mistral AI模型 / 大白话注释：法国的AI公司Mistral
    "huggingface",                                                             # 正经注释：HuggingFace模型平台 / 大白话注释：最大的开源AI模型社区
    "groq",                                                                    # 正经注释：Groq高速推理平台 / 大白话注释：号称推理速度超快的AI平台
    "bedrock",                                                                 # 正经注释：AWS Bedrock模型服务 / 大白话注释：亚马逊云上的AI服务
    "dashscope",                                                               # 正经注释：阿里云百炼（DashScope） / 大白话注释：阿里云的AI大模型服务
    "xai",                                                                     # 正经注释：xAI（Grok模型） / 大白话注释：马斯克搞的AI公司
    "deepseek",                                                                # 正经注释：DeepSeek深度求索 / 大白话注释：国产AI大模型深度求索
    "litellm",                                                                 # 正经注释：LiteLLM统一网关 / 大白话注释：一个统一的AI模型调用中间件
    "gigachat",                                                                # 正经注释：GigaChat（Sber） / 大白话注释：俄罗斯的AI聊天模型
    "openrouter",                                                              # 正经注释：OpenRouter模型路由 / 大白话注释：一个帮你选最便宜模型的路由服务
    "vllm_openai",                                                             # 正经注释：vLLM（OpenAI兼容接口） / 大白话注释：用vLLM部署的兼容OpenAI接口的服务
    "aimlapi",                                                                 # 正经注释：AI/ML API平台 / 大白话注释：一个提供各种AI模型API的平台
    "netmind",                                                                 # 正经注释：NetMind AI平台 / 大白话注释：又一个AI模型平台
    "forge",                                                                   # 正经注释：Forge（TensorBlock） / 大白话注释：TensorBlock提供的AI推理服务
    "avian",                                                                   # 正经注释：Avian AI平台 / 大白话注释：Avian提供的AI服务
    "minimax",                                                                 # 正经注释：MiniMax（稀宇科技） / 大白话注释：国产AI大模型MiniMax
}

NO_SUPPORT_TEMPERATURE_MODELS = [                                              # 正经注释：不支持自定义温度参数的模型列表 / 大白话注释：这些模型不让调温度参数，它们自己定死了
    "deepseek/deepseek-reasoner",                                              # 正经注释：DeepSeek推理模型 / 大白话注释：深度求索的推理专用模型
    "o1-mini",                                                                 # 正经注释：OpenAI o1-mini / 大白话注释：OpenAI的小号推理模型
    "o1-mini-2024-09-12",                                                      # 正经注释：o1-mini特定版本 / 大白话注释：o1-mini的某个日期版本
    "o1",                                                                      # 正经注释：OpenAI o1 / 大白话注释：OpenAI的推理大模型
    "o1-2024-12-17",                                                           # 正经注释：o1特定版本 / 大白话注释：o1的某个日期版本
    "o3-mini",                                                                 # 正经注释：OpenAI o3-mini / 大白话注释：OpenAI的新一代小号推理模型
    "o3-mini-2025-01-31",                                                      # 正经注释：o3-mini特定版本 / 大白话注释：o3-mini的某个日期版本
    "o1-preview",                                                              # 正经注释：o1预览版 / 大白话注释：o1的早期测试版
    "o3",                                                                      # 正经注释：OpenAI o3 / 大白话注释：OpenAI的新一代推理大模型
    "o3-2025-04-16",                                                           # 正经注释：o3特定版本 / 大白话注释：o3的某个日期版本
    "o4-mini",                                                                 # 正经注释：OpenAI o4-mini / 大白话注释：OpenAI的o4小号推理模型
    "o4-mini-2025-04-16",                                                      # 正经注释：o4-mini特定版本 / 大白话注释：o4-mini的某个日期版本
    # GPT-5 family: OpenAI enforces default temperature only                    # 正经注释：GPT-5系列模型仅使用默认温度值 / 大白话注释：GPT-5家族的模型也被锁死了温度
    "gpt-5",                                                                   # 正经注释：GPT-5模型 / 大白话注释：OpenAI的GPT-5
    "gpt-5-mini",                                                              # 正经注释：GPT-5-mini模型 / 大白话注释：GPT-5的小号版本
]

SUPPORT_REASONING_EFFORT_MODELS = [                                            # 正经注释：支持推理努力程度（reasoning_effort）参数的模型列表 / 大白话注释：这些模型可以调节"你给我多认真想"这个参数
    "o3-mini",                                                                 # 正经注释：o3-mini支持推理努力程度 / 大白话注释：o3-mini可以调思考力度
    "o3-mini-2025-01-31",                                                      # 正经注释：o3-mini特定版本 / 大白话注释：o3-mini的某个日期版本
    "o3",                                                                      # 正经注释：o3支持推理努力程度 / 大白话注释：o3可以调思考力度
    "o3-2025-04-16",                                                           # 正经注释：o3特定版本 / 大白话注释：o3的某个日期版本
    "o4-mini",                                                                 # 正经注释：o4-mini支持推理努力程度 / 大白话注释：o4-mini可以调思考力度
    "o4-mini-2025-04-16",                                                      # 正经注释：o4-mini特定版本 / 大白话注释：o4-mini的某个日期版本
]

class ReasoningEfforts(Enum):                                                  # 正经注释：推理努力程度枚举类 / 大白话注释：定义模型思考力度的高中低三档
    High = "high"                                                              # 正经注释：高努力程度 / 大白话注释：让模型使劲想
    Medium = "medium"                                                          # 正经注释：中等努力程度 / 大白话注释：让模型正常想
    Low = "low"                                                                # 正经注释：低努力程度 / 大白话注释：让模型随便想想就行


class ChatLogger:                                                              # 正经注释：聊天日志记录器，用于记录所有聊天请求及响应和调用栈 / 大白话注释：聊天记录小助手，把所有对话和返回结果都记下来
    """聊天日志记录工具类。        # 正经注释：辅助工具类，记录所有聊天请求、对应响应及调用栈信息 / 大白话注释：专门负责把每次聊天的来龙去脉都写进日志文件里"""

    def __init__(self, fname: str):                                            # 正经注释：初始化日志记录器 / 大白话注释：告诉它日志写到哪个文件
        self.fname = fname                                                     # 正经注释：日志文件名 / 大白话注释：日志文件路径
        self._lock = asyncio.Lock()                                            # 正经注释：异步锁，防止并发写入冲突 / 大白话注释：一把锁，防止多人同时写文件搞乱了

    async def log_request(self, messages, response):                           # 正经注释：异步记录请求和响应 / 大白话注释：把发出去的消息和收到的回复都记下来
        async with self._lock:                                                 # 正经注释：获取异步锁 / 大白话注释：先锁上，别人别来捣乱
            async with aiofiles.open(self.fname, mode="a", encoding="utf-8") as handle:  # 正经注释：以追加模式异步打开日志文件 / 大白话注释：打开日志文件，往后面追加内容
                await handle.write(json.dumps({                                # 正经注释：将日志信息序列化为JSON并写入 / 大白话注释：把信息变成JSON格式写进文件
                    "messages": messages,                                      # 正经注释：请求消息列表 / 大白话注释：发给模型的消息
                    "response": response,                                      # 正经注释：模型响应内容 / 大白话注释：模型回复的内容
                    "stacktrace": traceback.format_exc()                       # 正经注释：调用时的堆栈跟踪 / 大白话注释：出错时的调用路径
                }) + "\n")                                                     # 正经注释：每条记录后添加换行符 / 大白话注释：写完一条加个回车

class GenericLLMProvider:                                                      # 正经注释：通用大语言模型提供者，封装多种LLM的统一调用接口 / 大白话注释：万能AI模型适配器，不管啥模型都能用统一方式调用

    def __init__(self, llm, chat_log: str | None = None,  verbose: bool = True):  # 正经注释：初始化通用LLM提供者 / 大白话注释：把AI模型包装起来，准备好日志和详细输出
        self.llm = llm                                                         # 正经注释：LangChain聊天模型实例 / 大白话注释：真正的AI模型对象
        self.chat_logger = ChatLogger(chat_log) if chat_log else None          # 正经注释：聊天日志记录器（可选） / 大白话注释：如果有日志路径就创建记录器，没有就拉倒
        self.verbose = verbose                                                 # 正经注释：是否输出详细信息 / 大白话注释：要不要打印详细过程
        self.last_usage_metadata: dict[str, Any] | None = None                 # 正经注释：上次调用的用量元数据（token数等） / 大白话注释：上次调用用了多少token的记录
        self.last_response_metadata: dict[str, Any] = {}                       # 正经注释：上次调用的响应元数据 / 大白话注释：上次调用的返回信息（不含用量）

    def _reset_last_response_metadata(self) -> None:                           # 正经注释：重置上次响应元数据 / 大白话注释：清空之前的记录，准备记录新的
        self.last_usage_metadata = None                                        # 正经注释：清空用量元数据 / 大白话注释：token用量记录清零
        self.last_response_metadata = {}                                       # 正经注释：清空响应元数据 / 大白话注释：返回信息清空

    def _capture_response_metadata(self, message: Any) -> None:                # 正经注释：从响应消息中提取并保存元数据 / 大白话注释：把AI回复里附带的信息扒下来存好
        usage_metadata = getattr(message, "usage_metadata", None)              # 正经注释：获取用量元数据属性 / 大白话注释：看看回复里有没有token用量信息
        if usage_metadata:                                                     # 正经注释：如果存在用量元数据 / 大白话注释：如果有用量信息的话
            if hasattr(usage_metadata, "model_dump"):                          # 正经注释：检查是否有Pydantic序列化方法 / 大白话注释：看看能不能转成字典
                usage_metadata = usage_metadata.model_dump()                   # 正经注释：使用model_dump序列化为字典 / 大白话注释：转成字典
            self.last_usage_metadata = dict(usage_metadata)                    # 正经注释：保存用量元数据 / 大白话注释：存起来

        response_metadata = getattr(message, "response_metadata", None)        # 正经注释：获取响应元数据属性 / 大白话注释：看看回复里有没有其他附带信息
        if response_metadata:                                                  # 正经注释：如果存在响应元数据 / 大白话注释：如果有的话
            if hasattr(response_metadata, "model_dump"):                       # 正经注释：检查是否有Pydantic序列化方法 / 大白话注释：看看能不能转成字典
                response_metadata = response_metadata.model_dump()             # 正经注释：使用model_dump序列化为字典 / 大白话注释：转成字典
            self.last_response_metadata = {                                    # 正经注释：合并保存响应元数据 / 大白话注释：把新旧信息合在一起存起来
                **self.last_response_metadata,                                 # 正经注释：保留已有的元数据 / 大白话注释：之前的记录别丢了
                **dict(response_metadata),                                     # 正经注释：加入新的元数据 / 大白话注释：加上新的信息
            }                                                                  # 正经注释：元数据合并完成 / 大白话注释：合并完毕

    @classmethod                                                               # 正经注释：类方法装饰器，可通过类名直接调用 / 大白话注释：不用创建对象就能调用的方法
    def from_provider(cls, provider: str, chat_log: str | None = None, verbose: bool=True, **kwargs: Any):  # 正经注释：根据提供者名称创建对应LLM实例的工厂方法 / 大白话注释：告诉它你要用哪个AI公司的模型，它帮你创建好
        if provider == "openai":                                               # 正经注释：OpenAI提供者 / 大白话注释：如果选的是OpenAI
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看需要的包装了没
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用

            # Support custom OpenAI-compatible APIs via OPENAI_BASE_URL        # 正经注释：支持通过环境变量OPENAI_BASE_URL使用自定义的OpenAI兼容API / 大白话注释：如果你用的是兼容OpenAI的其他服务，可以通过环境变量指定地址
            if "openai_api_base" not in kwargs and os.environ.get("OPENAI_BASE_URL"):  # 正经注释：如果未指定API基础地址且环境变量中存在 / 大白话注释：如果没手动设地址但环境变量里有
                kwargs["openai_api_base"] = os.environ["OPENAI_BASE_URL"]      # 正经注释：使用环境变量中的API基础地址 / 大白话注释：就用环境变量里的地址

            llm = ChatOpenAI(**kwargs)                                         # 正经注释：创建OpenAI聊天模型实例 / 大白话注释：创建OpenAI模型对象
        elif provider == "anthropic":                                          # 正经注释：Anthropic（Claude）提供者 / 大白话注释：如果选的是Anthropic的Claude
            _check_pkg("langchain_anthropic")                                  # 正经注释：检查并安装langchain_anthropic包 / 大白话注释：先看看需要的包装了没
            from langchain_anthropic import ChatAnthropic                      # 正经注释：导入Anthropic聊天模型 / 大白话注释：把Claude的聊天模型拿来用

            llm = ChatAnthropic(**kwargs)                                      # 正经注释：创建Anthropic聊天模型实例 / 大白话注释：创建Claude模型对象
        elif provider == "azure_openai":                                       # 正经注释：Azure OpenAI提供者 / 大白话注释：如果用的是微软云上的OpenAI
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看需要的包装了没
            from langchain_openai import AzureChatOpenAI                       # 正经注释：导入Azure OpenAI聊天模型 / 大白话注释：把Azure版OpenAI的模型拿来用

            if "model" in kwargs:                                              # 正经注释：如果参数中指定了模型名称 / 大白话注释：如果你告诉了它要用哪个模型
                model_name = kwargs.get("model", None)                         # 正经注释：获取模型名称 / 大白话注释：把模型名拿出来
                kwargs = {"azure_deployment": model_name, **kwargs}            # 正经注释：将模型名映射为Azure部署名 / 大白话注释：Azure那边叫"部署名"，所以换个名字

            llm = AzureChatOpenAI(**kwargs)                                    # 正经注释：创建Azure OpenAI聊天模型实例 / 大白话注释：创建Azure版OpenAI模型对象
        elif provider == "cohere":                                             # 正经注释：Cohere提供者 / 大白话注释：如果选的是Cohere
            _check_pkg("langchain_cohere")                                     # 正经注释：检查并安装langchain_cohere包 / 大白话注释：先看看需要的包装了没
            from langchain_cohere import ChatCohere                            # 正经注释：导入Cohere聊天模型 / 大白话注释：把Cohere的聊天模型拿来用

            llm = ChatCohere(**kwargs)                                         # 正经注释：创建Cohere聊天模型实例 / 大白话注释：创建Cohere模型对象
        elif provider == "google_vertexai":                                    # 正经注释：Google Vertex AI提供者 / 大白话注释：如果用的是谷歌云Vertex AI
            _check_pkg("langchain_google_vertexai")                            # 正经注释：检查并安装langchain_google_vertexai包 / 大白话注释：先看看需要的包装了没
            from langchain_google_vertexai import ChatVertexAI                 # 正经注释：导入Vertex AI聊天模型 / 大白话注释：把谷歌Vertex的聊天模型拿来用

            llm = ChatVertexAI(**kwargs)                                       # 正经注释：创建Vertex AI聊天模型实例 / 大白话注释：创建Vertex AI模型对象
        elif provider == "google_genai":                                       # 正经注释：Google Generative AI（Gemini）提供者 / 大白话注释：如果用的是谷歌的Gemini
            _check_pkg("langchain_google_genai")                               # 正经注释：检查并安装langchain_google_genai包 / 大白话注释：先看看需要的包装了没
            from langchain_google_genai import ChatGoogleGenerativeAI           # 正经注释：导入Google生成式AI聊天模型 / 大白话注释：把Gemini的聊天模型拿来用

            llm = ChatGoogleGenerativeAI(**kwargs)                             # 正经注释：创建Google生成式AI聊天模型实例 / 大白话注释：创建Gemini模型对象
        elif provider == "fireworks":                                          # 正经注释：Fireworks AI提供者 / 大白话注释：如果用的是Fireworks
            _check_pkg("langchain_fireworks")                                  # 正经注释：检查并安装langchain_fireworks包 / 大白话注释：先看看需要的包装了没
            from langchain_fireworks import ChatFireworks                      # 正经注释：导入Fireworks聊天模型 / 大白话注释：把Fireworks的聊天模型拿来用

            llm = ChatFireworks(**kwargs)                                      # 正经注释：创建Fireworks聊天模型实例 / 大白话注释：创建Fireworks模型对象
        elif provider == "ollama":                                             # 正经注释：Ollama本地模型提供者 / 大白话注释：如果用的是自己电脑上的Ollama
            _check_pkg("langchain_community")                                  # 正经注释：检查并安装langchain_community包 / 大白话注释：先看看社区包装了没
            _check_pkg("langchain_ollama")                                     # 正经注释：检查并安装langchain_ollama包 / 大白话注释：再看看Ollama包装了没
            from langchain_ollama import ChatOllama                            # 正经注释：导入Ollama聊天模型 / 大白话注释：把Ollama的聊天模型拿来用

            llm = ChatOllama(base_url=os.environ["OLLAMA_BASE_URL"], **kwargs) # 正经注释：使用环境变量中的Ollama服务地址创建实例 / 大白话注释：告诉它Ollama跑在哪，创建模型对象
        elif provider == "together":                                           # 正经注释：Together AI提供者 / 大白话注释：如果用的是Together
            _check_pkg("langchain_together")                                   # 正经注释：检查并安装langchain_together包 / 大白话注释：先看看需要的包装了没
            from langchain_together import ChatTogether                        # 正经注释：导入Together聊天模型 / 大白话注释：把Together的聊天模型拿来用

            llm = ChatTogether(**kwargs)                                       # 正经注释：创建Together聊天模型实例 / 大白话注释：创建Together模型对象
        elif provider == "mistralai":                                          # 正经注释：Mistral AI提供者 / 大白话注释：如果用的是法国的Mistral
            _check_pkg("langchain_mistralai")                                  # 正经注释：检查并安装langchain_mistralai包 / 大白话注释：先看看需要的包装了没
            from langchain_mistralai import ChatMistralAI                      # 正经注释：导入Mistral聊天模型 / 大白话注释：把Mistral的聊天模型拿来用

            # Support custom Mistral-compatible APIs via MISTRAL_BASE_URL      # 正经注释：支持通过环境变量MISTRAL_BASE_URL使用自定义的Mistral兼容API / 大白话注释：如果你用的是兼容Mistral的其他服务，可以指定地址
            if "endpoint" not in kwargs and "base_url" not in kwargs and os.environ.get("MISTRAL_BASE_URL"):  # 正经注释：如果未指定端点且环境变量中存在 / 大白话注释：如果没手动设地址但环境变量里有
                kwargs["endpoint"] = os.environ["MISTRAL_BASE_URL"]            # 正经注释：使用环境变量中的端点地址 / 大白话注释：就用环境变量里的地址

            llm = ChatMistralAI(**kwargs)                                      # 正经注释：创建Mistral聊天模型实例 / 大白话注释：创建Mistral模型对象
        elif provider == "huggingface":                                        # 正经注释：HuggingFace提供者 / 大白话注释：如果用的是HuggingFace上的模型
            _check_pkg("langchain_huggingface")                                # 正经注释：检查并安装langchain_huggingface包 / 大白话注释：先看看需要的包装了没
            from langchain_huggingface import ChatHuggingFace                  # 正经注释：导入HuggingFace聊天模型 / 大白话注释：把HuggingFace的聊天模型拿来用

            if "model" in kwargs or "model_name" in kwargs:                    # 正经注释：如果参数中指定了模型 / 大白话注释：如果你告诉了它要用哪个模型
                model_id = kwargs.pop("model", None) or kwargs.pop("model_name", None)  # 正经注释：提取并移除模型名称参数 / 大白话注释：把模型名拿出来，参数里就不需要了
                kwargs = {"model_id": model_id, **kwargs}                      # 正经注释：将模型名映射为model_id / 大白话注释：HuggingFace叫model_id，换个名字
            llm = ChatHuggingFace(**kwargs)                                    # 正经注释：创建HuggingFace聊天模型实例 / 大白话注释：创建HuggingFace模型对象
        elif provider == "groq":                                               # 正经注释：Groq提供者 / 大白话注释：如果用的是超快的Groq
            _check_pkg("langchain_groq")                                       # 正经注释：检查并安装langchain_groq包 / 大白话注释：先看看需要的包装了没
            from langchain_groq import ChatGroq                                # 正经注释：导入Groq聊天模型 / 大白话注释：把Groq的聊天模型拿来用

            llm = ChatGroq(**kwargs)                                           # 正经注释：创建Groq聊天模型实例 / 大白话注释：创建Groq模型对象
        elif provider == "bedrock":                                            # 正经注释：AWS Bedrock提供者 / 大白话注释：如果用的是亚马逊云的Bedrock
            _check_pkg("langchain_aws")                                        # 正经注释：检查并安装langchain_aws包 / 大白话注释：先看看AWS的包装了没
            from langchain_aws import ChatBedrock                              # 正经注释：导入Bedrock聊天模型 / 大白话注释：把Bedrock的聊天模型拿来用

            if "model" in kwargs or "model_name" in kwargs:                    # 正经注释：如果参数中指定了模型 / 大白话注释：如果你告诉了它要用哪个模型
                model_id = kwargs.pop("model", None) or kwargs.pop("model_name", None)  # 正经注释：提取并移除模型名称参数 / 大白话注释：把模型名拿出来
                kwargs = {"model_id": model_id, "model_kwargs": kwargs}        # 正经注释：将参数包装为Bedrock所需的格式 / 大白话注释：Bedrock的参数格式比较特殊，要包一层
            llm = ChatBedrock(**kwargs)                                        # 正经注释：创建Bedrock聊天模型实例 / 大白话注释：创建Bedrock模型对象
        elif provider == "dashscope":                                          # 正经注释：阿里云百炼（DashScope）提供者 / 大白话注释：如果用的是阿里云的百炼
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包（DashScope兼容OpenAI接口） / 大白话注释：百炼兼容OpenAI的接口，所以用OpenAI的包就行
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用

            llm = ChatOpenAI(openai_api_base='https://dashscope.aliyuncs.com/compatible-mode/v1',  # 正经注释：使用阿里云百炼的兼容端点 / 大白话注释：用阿里云的API地址
                     openai_api_key=os.environ["DASHSCOPE_API_KEY"],            # 正经注释：从环境变量获取DashScope API密钥 / 大白话注释：用阿里云的密钥
                     **kwargs                                                  # 正经注释：传入其余参数 / 大白话注释：其他参数照传
                )                                                              # 正经注释：创建DashScope兼容的OpenAI实例 / 大白话注释：创建模型对象
        elif provider == "xai":                                                # 正经注释：xAI（Grok）提供者 / 大白话注释：如果用的是马斯克的xAI
            _check_pkg("langchain_xai")                                        # 正经注释：检查并安装langchain_xai包 / 大白话注释：先看看需要的包装了没
            from langchain_xai import ChatXAI                                  # 正经注释：导入xAI聊天模型 / 大白话注释：把xAI的聊天模型拿来用

            llm = ChatXAI(**kwargs)                                            # 正经注释：创建xAI聊天模型实例 / 大白话注释：创建xAI模型对象
        elif provider == "deepseek":                                           # 正经注释：DeepSeek提供者 / 大白话注释：如果用的是深度求索
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包（DeepSeek兼容OpenAI接口） / 大白话注释：深度求索也兼容OpenAI的接口
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用

            llm = ChatOpenAI(openai_api_base='https://api.deepseek.com',       # 正经注释：使用DeepSeek的API端点 / 大白话注释：用深度求索的API地址
                     openai_api_key=os.environ["DEEPSEEK_API_KEY"],            # 正经注释：从环境变量获取DeepSeek API密钥 / 大白话注释：用深度求索的密钥
                     **kwargs                                                  # 正经注释：传入其余参数 / 大白话注释：其他参数照传
                )                                                              # 正经注释：创建DeepSeek兼容的OpenAI实例 / 大白话注释：创建模型对象
        elif provider == "litellm":                                            # 正经注释：LiteLLM统一网关提供者 / 大白话注释：如果用的是LiteLLM这个中间件
            _check_pkg("langchain_community")                                  # 正经注释：检查并安装langchain_community包 / 大白话注释：先看看社区包装了没
            from langchain_community.chat_models.litellm import ChatLiteLLM    # 正经注释：导入LiteLLM聊天模型 / 大白话注释：把LiteLLM的聊天模型拿来用

            llm = ChatLiteLLM(**kwargs)                                        # 正经注释：创建LiteLLM聊天模型实例 / 大白话注释：创建LiteLLM模型对象
        elif provider == "gigachat":                                           # 正经注释：GigaChat提供者 / 大白话注释：如果用的是俄罗斯的GigaChat
            _check_pkg("langchain_gigachat")                                   # 正经注释：检查并安装langchain_gigachat包 / 大白话注释：先看看需要的包装了没
            from langchain_gigachat.chat_models import GigaChat                # 正经注释：导入GigaChat聊天模型 / 大白话注释：把GigaChat的聊天模型拿来用

            kwargs.pop("model", None) # Use env GIGACHAT_MODEL=GigaChat-Max   # 正经注释：移除model参数，使用环境变量GIGACHAT_MODEL指定模型 / 大白话注释：不用传模型名，它会从环境变量里自己找
            llm = GigaChat(**kwargs)                                           # 正经注释：创建GigaChat聊天模型实例 / 大白话注释：创建GigaChat模型对象
        elif provider == "openrouter":                                         # 正经注释：OpenRouter提供者 / 大白话注释：如果用的是OpenRouter路由服务
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看OpenAI的包装了没
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用
            from langchain_core.rate_limiters import InMemoryRateLimiter       # 正经注释：导入内存速率限制器 / 大白话注释：用来控制调用频率的工具

            rps = float(os.environ["OPENROUTER_LIMIT_RPS"]) if "OPENROUTER_LIMIT_RPS" in os.environ else 1.0  # 正经注释：从环境变量获取每秒请求数限制 / 大白话注释：每秒最多请求几次，默认1次

            rate_limiter = InMemoryRateLimiter(                                # 正经注释：创建内存速率限制器实例 / 大白话注释：创建限速器
                requests_per_second=rps,                                       # 正经注释：每秒允许的请求数 / 大白话注释：每秒放几个请求过去
                check_every_n_seconds=0.1,                                     # 正经注释：检查间隔时间 / 大白话注释：每0.1秒检查一次
                max_bucket_size=10,                                            # 正经注释：令牌桶最大容量 / 大白话注释：最多攒10个请求的额度
            )                                                                  # 正经注释：速率限制器配置完成 / 大白话注释：限速器配好了

            llm = ChatOpenAI(openai_api_base='https://openrouter.ai/api/v1',   # 正经注释：使用OpenRouter的API端点 / 大白话注释：用OpenRouter的API地址
                     request_timeout=180,                                      # 正经注释：请求超时时间为180秒 / 大白话注释：等3分钟还没结果就超时
                     openai_api_key=os.environ["OPENROUTER_API_KEY"],           # 正经注释：从环境变量获取OpenRouter API密钥 / 大白话注释：用OpenRouter的密钥
                     rate_limiter=rate_limiter,                                 # 正经注释：绑定速率限制器 / 大白话注释：把限速器挂上
                     **kwargs                                                  # 正经注释：传入其余参数 / 大白话注释：其他参数照传
                )                                                              # 正经注释：创建OpenRouter兼容的OpenAI实例 / 大白话注释：创建模型对象
        elif provider == "vllm_openai":                                        # 正经注释：vLLM（OpenAI兼容接口）提供者 / 大白话注释：如果用的是vLLM部署的服务
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看OpenAI的包装了没
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用
            llm = ChatOpenAI(                                                  # 正经注释：创建vLLM兼容的OpenAI实例 / 大白话注释：创建模型对象
                openai_api_key=os.environ["VLLM_OPENAI_API_KEY"],              # 正经注释：从环境变量获取vLLM API密钥 / 大白话注释：用vLLM的密钥
                openai_api_base=os.environ["VLLM_OPENAI_API_BASE"],            # 正经注释：从环境变量获取vLLM API基础地址 / 大白话注释：用vLLM的服务地址
                **kwargs                                                       # 正经注释：传入其余参数 / 大白话注释：其他参数照传
            )                                                                  # 正经注释：vLLM实例创建完成 / 大白话注释：模型对象创建好了
        elif provider == "aimlapi":                                            # 正经注释：AI/ML API提供者 / 大白话注释：如果用的是AI/ML API平台
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看OpenAI的包装了没
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用

            llm = ChatOpenAI(openai_api_base='https://api.aimlapi.com/v1',     # 正经注释：使用AI/ML API的端点 / 大白话注释：用AI/ML API的地址
                             openai_api_key=os.environ["AIMLAPI_API_KEY"],     # 正经注释：从环境变量获取AIMLAPI密钥 / 大白话注释：用AI/ML API的密钥
                             **kwargs                                           # 正经注释：传入其余参数 / 大白话注释：其他参数照传
                             )                                                  # 正经注释：创建AI/ML API兼容的OpenAI实例 / 大白话注释：创建模型对象
        elif provider == "forge":                                              # 正经注释：Forge（TensorBlock）提供者 / 大白话注释：如果用的是TensorBlock的Forge服务
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看OpenAI的包装了没
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用

            llm = ChatOpenAI(openai_api_base='https://api.forge.tensorblock.co/v1',  # 正经注释：使用Forge的API端点 / 大白话注释：用Forge的API地址
                     openai_api_key=os.environ["FORGE_API_KEY"],               # 正经注释：从环境变量获取Forge API密钥 / 大白话注释：用Forge的密钥
                     **kwargs                                                  # 正经注释：传入其余参数 / 大白话注释：其他参数照传
                )                                                              # 正经注释：创建Forge兼容的OpenAI实例 / 大白话注释：创建模型对象
        elif provider == "avian":                                              # 正经注释：Avian AI提供者 / 大白话注释：如果用的是Avian的服务
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看OpenAI的包装了没
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用

            llm = ChatOpenAI(openai_api_base='https://api.avian.io/v1',        # 正经注释：使用Avian的API端点 / 大白话注释：用Avian的API地址
                     openai_api_key=os.environ["AVIAN_API_KEY"],               # 正经注释：从环境变量获取Avian API密钥 / 大白话注释：用Avian的密钥
                     **kwargs                                                  # 正经注释：传入其余参数 / 大白话注释：其他参数照传
                )                                                              # 正经注释：创建Avian兼容的OpenAI实例 / 大白话注释：创建模型对象
        elif provider == "minimax":                                            # 正经注释：MiniMax（稀宇科技）提供者 / 大白话注释：如果用的是MiniMax
            _check_pkg("langchain_openai")                                     # 正经注释：检查并安装langchain_openai包 / 大白话注释：先看看OpenAI的包装了没
            from langchain_openai import ChatOpenAI                            # 正经注释：导入OpenAI聊天模型 / 大白话注释：把OpenAI的聊天模型拿来用

            llm = ChatOpenAI(openai_api_base='https://api.minimax.io/v1',      # 正经注释：使用MiniMax的API端点 / 大白话注释：用MiniMax的API地址
                     openai_api_key=os.environ["MINIMAX_API_KEY"],             # 正经注释：从环境变量获取MiniMax API密钥 / 大白话注释：用MiniMax的密钥
                     **kwargs                                                  # 正经注释：传入其余参数 / 大白话注释：其他参数照传
                )                                                              # 正经注释：创建MiniMax兼容的OpenAI实例 / 大白话注释：创建模型对象
        elif provider == 'netmind':                                            # 正经注释：NetMind AI提供者 / 大白话注释：如果用的是NetMind
            _check_pkg("langchain_netmind")                                    # 正经注释：检查并安装langchain_netmind包 / 大白话注释：先看看NetMind的包装了没
            from langchain_netmind import ChatNetmind                          # 正经注释：导入NetMind聊天模型 / 大白话注释：把NetMind的聊天模型拿来用

            llm = ChatNetmind(**kwargs)                                        # 正经注释：创建NetMind聊天模型实例 / 大白话注释：创建NetMind模型对象
        else:                                                                  # 正经注释：不支持的提供者 / 大白话注释：选了个不认识的供应商
            supported = ", ".join(_SUPPORTED_PROVIDERS)                        # 正经注释：拼接所有支持的提供者名称 / 大白话注释：把所有支持的供应商列出来
            raise ValueError(                                                  # 正经注释：抛出值错误异常 / 大白话注释：报错！
                f"Unsupported {provider}.\n\nSupported model providers are: {supported}"  # 正经注释：提示不支持的提供者及可选列表 / 大白话注释：告诉用户这个供应商不支持，并列出能用的
            )                                                                  # 正经注释：异常抛出完成 / 大白话注释：报错完毕
        return cls(llm, chat_log, verbose=verbose)                             # 正经注释：使用创建的LLM实例构造GenericLLMProvider对象并返回 / 大白话注释：把模型对象包好返回


    async def get_chat_response(self, messages, stream, websocket=None, **kwargs):  # 正经注释：获取聊天响应，支持流式和非流式两种模式 / 大白话注释：跟AI聊天要回复，可以一次性给也可以一边生成一边给
        self._reset_last_response_metadata()                                   # 正经注释：重置响应元数据 / 大白话注释：清空之前的记录
        if not stream:                                                         # 正经注释：非流式模式 / 大白话注释：如果不是流式输出
            # Getting output from the model chain using ainvoke for asynchronous invoking  # 正经注释：使用ainvoke方法异步调用模型链获取输出 / 大白话注释：等模型全部生成完了再给结果
            output = await self.llm.ainvoke(messages, **kwargs)                # 正经注释：异步调用LLM获取完整响应 / 大白话注释：把消息发给模型，等回复
            self._capture_response_metadata(output)                            # 正经注释：捕获响应元数据 / 大白话注释：把回复里附带的信息存起来

            res = output.content                                               # 正经注释：提取响应文本内容 / 大白话注释：把回复的文字拿出来

        else:                                                                  # 正经注释：流式模式 / 大白话注释：如果是流式输出
            res = await self.stream_response(messages, websocket, **kwargs)    # 正经注释：调用流式响应方法 / 大白话注释：一边生成一边输出

        if self.chat_logger:                                                   # 正经注释：如果配置了聊天日志记录器 / 大白话注释：如果有日志记录器的话
            await self.chat_logger.log_request(messages, res)                  # 正经注释：记录请求和响应 / 大白话注释：把这次对话记下来

        return res                                                             # 正经注释：返回响应文本 / 大白话注释：把结果返回

    async def stream_response(self, messages, websocket=None, **kwargs):       # 正经注释：流式获取模型响应，逐段输出 / 大白话注释：像打字机一样一个字一个字地输出模型的回复
        self._reset_last_response_metadata()                                   # 正经注释：重置响应元数据 / 大白话注释：清空之前的记录
        paragraph = ""                                                         # 正经注释：当前段落缓存 / 大白话注释：攒着当前这一段文字
        response = ""                                                          # 正经注释：完整响应文本 / 大白话注释：攒着所有收到的文字

        # Streaming the response using the chain astream method from langchain  # 正经注释：使用LangChain的astream方法进行流式响应 / 大白话注释：用LangChain的流式接口来接收
        async for chunk in self.llm.astream(messages, **kwargs):               # 正经注释：异步迭代模型流式输出 / 大白话注释：每次收到一小段就处理一小段
            self._capture_response_metadata(chunk)                             # 正经注释：从每个数据块中捕获元数据 / 大白话注释：把附带信息存起来
            content = chunk.content                                            # 正经注释：提取数据块中的文本内容 / 大白话注释：把这段文字拿出来
            if not content:                                                    # 正经注释：如果内容为空则跳过 / 大白话注释：空内容就跳过
                continue                                                       # 正经注释：跳过此数据块 / 大白话注释：继续等下一个
            response += content                                                # 正经注释：追加到完整响应 / 大白话注释：把这段文字加到总结果里
            paragraph += content                                               # 正经注释：追加到当前段落 / 大白话注释：也加到当前段落里
            if "\n" in paragraph:                                              # 正经注释：如果段落中包含换行符 / 大白话注释：如果攒到换行了
                await self._send_output(paragraph, websocket)                  # 正经注释：发送当前段落输出 / 大白话注释：就把这一段发出去
                paragraph = ""                                                 # 正经注释：清空段落缓存 / 大白话注释：段落清空，准备攒下一段

        if paragraph:                                                          # 正经注释：如果还有剩余未发送的段落 / 大白话注释：如果最后还有没发完的文字
            await self._send_output(paragraph, websocket)                      # 正经注释：发送剩余段落 / 大白话注释：把最后这段也发出去

        return response                                                        # 正经注释：返回完整响应文本 / 大白话注释：把所有文字返回

    async def _send_output(self, content, websocket=None):                     # 正经注释：发送输出内容，通过WebSocket或终端打印 / 大白话注释：把文字发出去，有WebSocket就走WebSocket，没有就打印到屏幕
        if websocket is not None:                                              # 正经注释：如果WebSocket连接存在 / 大白话注释：如果有WebSocket连接的话
            await websocket.send_json({"type": "report", "output": content})   # 正经注释：通过WebSocket发送JSON格式的报告输出 / 大白话注释：把内容以JSON格式通过WebSocket发出去
        elif self.verbose:                                                     # 正经注释：否则如果开启了详细输出模式 / 大白话注释：没有WebSocket的话，看看要不要打印到屏幕
            print(f"{Fore.GREEN}{content}{Style.RESET_ALL}", flush=True)       # 正经注释：以绿色文字打印内容并立即刷新输出 / 大白话注释：用绿色字打印到屏幕上


def _check_pkg(pkg: str) -> None:                                             # 正经注释：检查Python包是否已安装，若未安装则自动安装 / 大白话注释：看看这个包装了没，没装就帮你装上
    if not importlib.util.find_spec(pkg):                                      # 正经注释：查找包的模块规格，判断是否已安装 / 大白话注释：找找这个包在不在
        pkg_kebab = pkg.replace("_", "-")                                      # 正经注释：将包名中的下划线替换为连字符（pip安装格式） / 大白话注释：包名格式转换，比如langchain_openai变成langchain-openai
        # Import colorama and initialize it                                    # 正经注释：导入colorama并初始化 / 大白话注释：导入彩色打印工具并初始化
        init(autoreset=True)                                                   # 正经注释：自动重置颜色设置 / 大白话注释：每次打印完自动恢复默认颜色

        try:                                                                   # 正经注释：尝试安装包 / 大白话注释：试试装
            print(f"{Fore.YELLOW}Installing {pkg_kebab}...{Style.RESET_ALL}")  # 正经注释：以黄色打印安装提示信息 / 大白话注释：黄色字告诉你正在装
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", pkg_kebab])  # 正经注释：使用pip安装并升级指定包 / 大白话注释：调用pip帮你装这个包
            print(f"{Fore.GREEN}Successfully installed {pkg_kebab}{Style.RESET_ALL}")  # 正经注释：以绿色打印安装成功信息 / 大白话注释：绿色字告诉你装好了

            # Try importing again after install                                # 正经注释：安装后重新尝试导入 / 大白话注释：装好了再试试导入
            importlib.import_module(pkg)                                       # 正经注释：导入刚安装的模块 / 大白话注释：把这个包导进来

        except subprocess.CalledProcessError:                                  # 正经注释：捕获子进程调用失败异常 / 大白话注释：如果装失败了
            raise ImportError(                                                 # 正经注释：抛出导入错误 / 大白话注释：报错！
                Fore.RED + f"Failed to install {pkg_kebab}. Please install manually with "  # 正经注释：提示安装失败，建议手动安装 / 大白话注释：红色的字告诉你装不上，你自己手动装吧
                f"`pip install -U {pkg_kebab}`"                                # 正经注释：提供手动安装命令 / 大白话注释：告诉你用这个命令装
            )                                                                  # 正经注释：异常抛出完成 / 大白话注释：报错完毕
