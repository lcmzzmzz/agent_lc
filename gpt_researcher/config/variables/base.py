"""
基础配置类型定义模块。

【正经注释】
本模块使用 TypedDict 定义 GPT Researcher 所有配置项的类型结构。
每个配置项都明确了其期望的数据类型，用于配置加载时的类型验证和转换。

【大白话注释】
这个文件就是一张"配置表"，定义了项目支持哪些配置项以及每项的类型。
比如 RETRIEVER 是字符串，MAX_ITERATIONS 是整数，方便程序自动检查配置对不对。
"""
from typing import Union, List, Dict, Any  # 正经注释：导入类型提示工具 / 大白话注释：类型标注工具箱
from typing_extensions import TypedDict  # 正经注释：导入 TypedDict，用于定义带类型提示的字典结构 / 大白话注释：用来定义"字典里每个键是什么类型"的特殊字典


class BaseConfig(TypedDict):
    """
    GPT Researcher 的基础配置类型定义。

    【正经注释】
    使用 TypedDict 声明所有配置项及其类型，作为配置字典的类型约束。
    所有配置键名使用大写，运行时通过 Config 类转为小写属性访问。

    【大白话注释】
    这就是配置的"表格模板"，列出了所有能设置的项和它们的类型。
    你可以把它当成一份"设置说明书"来看。
    """
    RETRIEVER: str  # 正经注释：搜索引擎/检索器名称，支持逗号分隔多个 / 大白话注释：用哪个搜索引擎找资料
    EMBEDDING: str  # 正经注释：嵌入模型配置，格式为 "provider:model" / 大白话注释：用哪个向量模型把文字变成数字
    SIMILARITY_THRESHOLD: float  # 正经注释：相似度过滤阈值 / 大白话注释：内容要跟问题多相关才保留，0.42 就是42%以上才要
    FAST_LLM: str  # 正经注释：快速 LLM 配置，用于轻量任务 / 大白话注释：干杂活用的快速模型
    SMART_LLM: str  # 正经注释：智能 LLM 配置，用于报告生成 / 大白话注释：写报告用的聪明模型
    STRATEGIC_LLM: str  # 正经注释：策略 LLM 配置，用于规划和推理 / 大白话注释：做规划用的策略模型
    FAST_TOKEN_LIMIT: int  # 正经注释：快速 LLM 的 token 上限 / 大白话注释：快速模型最多能处理多少字
    SMART_TOKEN_LIMIT: int  # 正经注释：智能 LLM 的 token 上限 / 大白话注释：聪明模型最多能处理多少字
    STRATEGIC_TOKEN_LIMIT: int  # 正经注释：策略 LLM 的 token 上限 / 大白话注释：策略模型最多能处理多少字
    BROWSE_CHUNK_MAX_LENGTH: int  # 正经注释：浏览内容的最大分块长度 / 大白话注释：网页内容一次最多读多少字符
    SUMMARY_TOKEN_LIMIT: int  # 正经注释：摘要的 token 上限 / 大白话注释：生成摘要最多用多少字
    TEMPERATURE: float  # 正经注释：LLM 生成的温度参数 / 大白话注释：模型回答有多"随机"，0=死板，1=放飞自我
    USER_AGENT: str  # 正经注释：HTTP 请求的 User-Agent 头 / 大白话注释：爬网页时假装自己是浏览器
    MAX_SEARCH_RESULTS_PER_QUERY: int  # 正经注释：每次搜索的最大结果数 / 大白话注释：每次搜索最多返回几条结果
    MEMORY_BACKEND: str  # 正经注释：记忆存储后端类型 / 大白话注释：记忆存在哪里（本地/数据库等）
    TOTAL_WORDS: int  # 正经注释：报告的目标总字数 / 大白话注释：报告大概写多少字
    REPORT_FORMAT: str  # 正经注释：报告格式（如 APA、MLA 等） / 大白话注释：报告用什么格式写
    CURATE_SOURCES: bool  # 正经注释：是否对来源进行精选过滤 / 大白话注释：要不要挑一挑，只保留高质量来源
    MAX_ITERATIONS: int  # 正经注释：最大研究迭代次数 / 大白话注释：最多反复搜索几轮
    LANGUAGE: str  # 正经注释：报告输出语言 / 大白话注释：报告用什么语言写
    AGENT_ROLE: Union[str, None]  # 正经注释：自定义代理角色提示词 / 大白话注释：给AI指定一个"人设"，比如"你是财经分析师"
    SCRAPER: str  # 正经注释：网页抓取器类型 / 大白话注释：用什么工具抓网页内容
    MAX_SCRAPER_WORKERS: int  # 正经注释：抓取器最大并发工作数 / 大白话注释：同时开几个线程去抓网页
    SCRAPER_RATE_LIMIT_DELAY: float  # 正经注释：抓取请求之间的最小延迟（秒） / 大白话注释：每次抓网页之间等几秒，别太快被封
    MAX_SUBTOPICS: int  # 正经注释：最大子主题数量 / 大白话注释：报告最多分几个小主题来写
    REPORT_SOURCE: Union[str, None]  # 正经注释：报告内容来源（web/local/hybrid 等） / 大白话注释：从哪找资料——网上、本地文件、还是都要
    DOC_PATH: str  # 正经注释：本地文档目录路径 / 大白话注释：本地文件放在哪个文件夹
    PROMPT_FAMILY: str  # 正经注释：提示词模板族名称 / 大白话注释：用哪套"话术模板"
    LLM_KWARGS: dict  # 正经注释：传递给 LLM 的额外参数 / 大白话注释：给大模型传的其他参数
    EMBEDDING_KWARGS: dict  # 正经注释：传递给嵌入模型的额外参数 / 大白话注释：给向量模型传的其他参数
    VERBOSE: bool  # 正经注释：是否启用详细日志输出 / 大白话注释：要不要打印详细信息
    DEEP_RESEARCH_CONCURRENCY: int  # 正经注释：深度研究的并发数 / 大白话注释：深度研究时同时跑几个任务
    DEEP_RESEARCH_DEPTH: int  # 正经注释：深度研究的递归深度 / 大白话注释：深度研究挖几层
    DEEP_RESEARCH_BREADTH: int  # 正经注释：深度研究的广度 / 大白话注释：深度研究每层展开几个方向
    MCP_SERVERS: List[Dict[str, Any]]  # 正经注释：MCP 服务器配置列表 / 大白话注释：MCP工具调用的服务器列表
    MCP_AUTO_TOOL_SELECTION: bool  # 正经注释：是否自动选择 MCP 工具 / 大白话注释：让AI自己选合适的工具，不用手动指定
    MCP_USE_LLM_ARGS: bool  # 正经注释：是否将 LLM 参数传递给 MCP 工具 / 大白话注释：MCP工具要不要用大模型的参数
    MCP_ALLOWED_ROOT_PATHS: List[str]  # 正经注释：MCP 服务器允许访问的根路径列表 / 大白话注释：MCP工具能访问哪些本地目录
    MCP_STRATEGY: str  # 正经注释：MCP 执行策略 / 大白话注释：MCP工具怎么执行——快速、深度还是关闭
    REASONING_EFFORT: str  # 正经注释：推理努力程度 / 大白话注释：让模型想多深——浅、中、深
    # Image generation settings
    IMAGE_GENERATION_MODEL: Union[str, None]  # 正经注释：图片生成模型名称 / 大白话注释：用哪个模型生成配图
    IMAGE_GENERATION_MAX_IMAGES: int  # 正经注释：每份报告最大生成图片数 / 大白话注释：一份报告最多配几张图
    IMAGE_GENERATION_ENABLED: bool  # 正经注释：是否启用图片生成 / 大白话注释：要不要自动给报告配图
    IMAGE_GENERATION_STYLE: str  # Image style: "dark", "light", or "auto"  # 正经注释：图片风格 / 大白话注释：图片什么风格——深色、浅色还是自动
    IMAGE_GENERATION_PROVIDER: str  # Image provider: "google" or "modelslab"  # 正经注释：图片生成服务提供商 / 大白话注释：用谁家的服务生成图片
