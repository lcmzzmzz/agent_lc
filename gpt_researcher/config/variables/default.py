"""
默认配置值定义模块。

【正经注释】
本模块定义了 GPT Researcher 的所有默认配置值。当用户未提供
自定义配置文件或环境变量时，将使用此处定义的默认值。
配置项的键名必须与 BaseConfig 中定义的类型一一对应。

【大白话注释】
这个文件就是"出厂设置"，列出了所有配置项的默认值。
你啥都不改的话，项目就用这些默认值运行。
"""
from .base import BaseConfig  # 正经注释：导入配置类型定义，确保默认值的类型约束 / 大白话注释：导入配置表模板，确保这里填的值类型对得上

DEFAULT_CONFIG: BaseConfig = {  # 正经注释：默认配置字典，类型受 BaseConfig 约束 / 大白话注释：这就是出厂设置表，所有默认值都在这
    "RETRIEVER": "tavily",  # 正经注释：默认使用 Tavily 搜索引擎 / 大白话注释：默认用 tavily 搜索
    "EMBEDDING": "openai:text-embedding-3-small",  # 正经注释：默认使用 OpenAI 的小型嵌入模型 / 大白话注释：默认用 OpenAI 的轻量向量模型
    "SIMILARITY_THRESHOLD": 0.42,  # 正经注释：默认相似度阈值 0.42 / 大白话注释：相关度超过42%的内容才保留
    "FAST_LLM": "openai:gpt-4o-mini",  # 正经注释：快速 LLM 默认使用 gpt-4o-mini / 大白话注释：干杂活默认用便宜快速的小模型
    "SMART_LLM": "openai:gpt-4.1",  # Has support for long responses (2k+ words).  # 正经注释：智能 LLM 默认使用 gpt-4.1，支持长响应 / 大白话注释：写报告默认用聪明的 gpt-4.1，能写长文
    "STRATEGIC_LLM": "openai:o4-mini",  # Can be used with o1 or o3, please note it will make tasks slower.  # 正经注释：策略 LLM 默认使用 o4-mini / 大白话注释：做规划默认用 o4-mini，会慢一些但更会思考
    "FAST_TOKEN_LIMIT": 3000,  # 正经注释：快速 LLM 最大 3000 token / 大白话注释：快速模型最多处理3000个token
    "SMART_TOKEN_LIMIT": 6000,  # 正经注释：智能 LLM 最大 6000 token / 大白话注释：聪明模型最多处理6000个token
    "STRATEGIC_TOKEN_LIMIT": 4000,  # 正经注释：策略 LLM 最大 4000 token / 大白话注释：策略模型最多处理4000个token
    "BROWSE_CHUNK_MAX_LENGTH": 8192,  # 正经注释：浏览分块最大 8192 字符 / 大白话注释：网页内容一次最多读8192字符
    "CURATE_SOURCES": False,  # 正经注释：默认不精选来源 / 大白话注释：默认不挑来源，全都要
    "SUMMARY_TOKEN_LIMIT": 700,  # 正经注释：摘要最大 700 token / 大白话注释：摘要最多700个token
    "TEMPERATURE": 0.4,  # 正经注释：默认温度 0.4，偏保守 / 大白话注释：默认温度0.4，回答比较稳定不太放飞
    "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",  # 正经注释：模拟 Edge 浏览器的 User-Agent / 大白话注释：假装自己是 Edge 浏览器去访问网页
    "MAX_SEARCH_RESULTS_PER_QUERY": 5,  # 正经注释：每次搜索最多 5 条结果 / 大白话注释：每次搜索拿5条结果
    "MEMORY_BACKEND": "local",  # 正经注释：默认使用本地内存后端 / 大白话注释：记忆存本地，不连数据库
    "TOTAL_WORDS": 1200,  # 正经注释：报告目标 1200 词 / 大白话注释：报告默认写1200字左右
    "REPORT_FORMAT": "APA",  # 正经注释：报告格式默认 APA / 大白话注释：报告用 APA 格式（学术论文那种）
    "MAX_ITERATIONS": 3,  # 正经注释：最多迭代 3 轮 / 大白话注释：最多反复搜索3轮
    "AGENT_ROLE": None,  # 正经注释：不指定代理角色 / 大白话注释：不给AI设人设，让它自由发挥
    "SCRAPER": "bs",  # 正经注释：默认使用 BeautifulSoup 抓取器 / 大白话注释：默认用 bs（BeautifulSoup）抓网页
    "MAX_SCRAPER_WORKERS": 15,  # 正经注释：最多 15 个抓取并发 / 大白话注释：同时开15个线程抓网页
    "SCRAPER_RATE_LIMIT_DELAY": 0.0,  # Minimum seconds between scraper requests (0 = no limit, useful for API rate limiting)  # 正经注释：抓取间隔 0 秒，不限制 / 大白话注释：抓网页不等，连续抓
    "MAX_SUBTOPICS": 3,  # 正经注释：最多 3 个子主题 / 大白话注释：报告最多分3个小题目
    "LANGUAGE": "english",  # 正经注释：默认输出英语 / 大白话注释：默认用英文写报告
    "REPORT_SOURCE": "web",  # 正经注释：默认从网络获取资料 / 大白话注释：默认从网上找资料
    "DOC_PATH": "./my-docs",  # 正经注释：本地文档默认路径 / 大白话注释：本地文件默认放在 ./my-docs 文件夹
    "PROMPT_FAMILY": "default",  # 正经注释：默认提示词模板族 / 大白话注释：用默认的那套话术模板
    "LLM_KWARGS": {},  # 正经注释：LLM 额外参数默认为空 / 大白话注释：不给大模型传额外参数
    "EMBEDDING_KWARGS": {},  # 正经注释：嵌入模型额外参数默认为空 / 大白话注释：不给向量模型传额外参数
    "VERBOSE": False,  # 正经注释：默认不输出详细日志 / 大白话注释：默认不打印啰嗦信息
    # Deep research specific settings
    "DEEP_RESEARCH_BREADTH": 3,  # 正经注释：深度研究每层展开 3 个方向 / 大白话注释：深度研究每层往3个方向展开
    "DEEP_RESEARCH_DEPTH": 2,  # 正经注释：深度研究递归 2 层 / 大白话注释：深度研究挖2层深
    "DEEP_RESEARCH_CONCURRENCY": 4,  # 正经注释：深度研究并发 4 个任务 / 大白话注释：深度研究同时跑4个任务

    # MCP retriever specific settings
    "MCP_SERVERS": [],  # List of predefined MCP server configurations  # 正经注释：默认无 MCP 服务器 / 大白话注释：默认没有配置MCP工具服务器
    "MCP_AUTO_TOOL_SELECTION": True,  # Whether to automatically select the best tool for a query  # 正经注释：默认自动选择工具 / 大白话注释：默认让AI自己选工具
    "MCP_ALLOWED_ROOT_PATHS": [],  # List of allowed root paths for local file access  # 正经注释：默认不允许访问本地路径 / 大白话注释：默认MCP不能访问本地文件
    "MCP_STRATEGY": "fast",  # MCP execution strategy: "fast", "deep", "disabled"  # 正经注释：默认快速策略 / 大白话注释：MCP默认用快速模式
    "REASONING_EFFORT": "medium",  # 正经注释：默认中等推理努力 / 大白话注释：默认让模型用中等深度思考

    # Image generation settings (optional - requires GOOGLE_API_KEY)
    # Free tier models: gemini-2.5-flash-image, gemini-2.0-flash-exp-image-generation
    # Paid tier models: imagen-4.0-generate-001, imagen-4.0-fast-generate-001
    "IMAGE_GENERATION_MODEL": "models/gemini-2.5-flash-image",  # 正经注释：默认使用 Gemini Flash 图片模型 / 大白话注释：默认用谷歌的免费图片模型
    "IMAGE_GENERATION_MAX_IMAGES": 3,  # Maximum number of images to generate per report  # 正经注释：每份报告最多生成 3 张图 / 大白话注释：一份报告最多配3张图
    "IMAGE_GENERATION_ENABLED": False,  # Master switch for inline image generation  # 正经注释：图片生成默认关闭 / 大白话注释：默认不开自动配图
    "IMAGE_GENERATION_STYLE": "dark",  # Image style: "dark" (matches app theme), "light", or "auto"  # 正经注释：默认深色风格 / 大白话注释：图片默认深色风格，配合深色主题
    "IMAGE_GENERATION_PROVIDER": "google",  # Image provider: "google" or "modelslab"  # 正经注释：默认使用 Google 生成图片 / 大白话注释：默认用谷歌的服务生成图片
}
