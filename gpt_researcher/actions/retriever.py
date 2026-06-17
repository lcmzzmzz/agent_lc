"""检索器工厂模块（Retriever Factory）
【正经注释】
本模块提供检索器的工厂函数，通过名称匹配创建对应的搜索引擎类实例。
支持 16 种检索器，使用 Python 3.10+ 的 match-case 语法进行模式匹配。
包含三个核心函数：get_retriever（按名称获取单个）、get_retrievers（按配置获取列表）、get_default_retriever（获取默认值）。
【大白话注释】
这个文件就是"搜索引擎的工厂"——你告诉它要哪个搜索引擎（Google、Bing、Tavily 等），它就给你创建一个。
"""


def get_retriever(retriever: str):
    """按名称获取检索器类
    【正经注释】使用 match-case 模式匹配，通过延迟导入避免加载所有检索器模块。
    【大白话注释】你说要哪个搜索引擎，就给你哪个。用到了才导入，省内存。
    Args:
        retriever: 检索器名称（大白话：搜索引擎的名字）
    Returns:
        检索器类 或 None（大白话：对应的搜索引擎类，不认识的返回 None）
    """
    match retriever:
        case "google":										# 正经注释：Google 自定义搜索 / 大白话注释：Google 搜索
            from gpt_researcher.retrievers import GoogleSearch

            return GoogleSearch
        case "searx":										# 正经注释：SearX 开源搜索引擎 / 大白话注释：SearX 搜索
            from gpt_researcher.retrievers import SearxSearch

            return SearxSearch
        case "searchapi":									# 正经注释：SearchAPI 服务 / 大白话注释：SearchAPI 搜索
            from gpt_researcher.retrievers import SearchApiSearch

            return SearchApiSearch
        case "serpapi":										# 正经注释：SerpAPI 服务 / 大白话注释：SerpAPI 搜索
            from gpt_researcher.retrievers import SerpApiSearch

            return SerpApiSearch
        case "serper":										# 正经注释：Serper API / 大白话注释：Serper 搜索
            from gpt_researcher.retrievers import SerperSearch

            return SerperSearch
        case "duckduckgo":									# 正经注释：DuckDuckGo 搜索 / 大白话注释：DuckDuckGo 搜索
            from gpt_researcher.retrievers import Duckduckgo

            return Duckduckgo
        case "bing":										# 正经注释：Bing 搜索 / 大白话注释：必应搜索
            from gpt_researcher.retrievers import BingSearch

            return BingSearch
        case "bocha":										# 正经注释：BoCha 搜索 / 大白话注释：BoCha 搜索
            from gpt_researcher.retrievers import BoChaSearch

            return BoChaSearch
        case "arxiv":										# 正经注释：arXiv 学术搜索 / 大白话注释：学术论文搜索
            from gpt_researcher.retrievers import ArxivSearch

            return ArxivSearch
        case "tavily":										# 正经注释：Tavily 搜索 API / 大白话注释：Tavily 搜索（默认搜索引擎）
            from gpt_researcher.retrievers import TavilySearch

            return TavilySearch
        case "exa":											# 正经注释：Exa 搜索 / 大白话注释：Exa 搜索
            from gpt_researcher.retrievers import ExaSearch

            return ExaSearch
        case "semantic_scholar":								# 正经注释：Semantic Scholar 学术搜索 / 大白话注释：学术文献搜索
            from gpt_researcher.retrievers import SemanticScholarSearch

            return SemanticScholarSearch
        case "pubmed_central":								# 正经注释：PubMed Central 医学文献 / 大白话注释：医学论文搜索
            from gpt_researcher.retrievers import PubMedCentralSearch

            return PubMedCentralSearch
        case "custom":										# 正经注释：用户自定义检索器 / 大白话注释：自定义搜索
            from gpt_researcher.retrievers import CustomRetriever

            return CustomRetriever
        case "mcp":											# 正经注释：Model Context Protocol 检索器 / 大白话注释：外部工具搜索
            from gpt_researcher.retrievers import MCPRetriever

            return MCPRetriever
        case "xquik":										# 正经注释：Xquik X/Twitter 搜索 / 大白话注释：推特搜索
            from gpt_researcher.retrievers import XquikSearch

            return XquikSearch
        case "openalex":									# 正经注释：OpenAlex 学术作品目录 / 大白话注释：开放学术搜索
            from gpt_researcher.retrievers import OpenAlexSearch

            return OpenAlexSearch

        case _:												# 正经注释：未匹配的名称返回 None / 大白话注释：不认识的搜索引擎，返回空
            return None


def get_retrievers(headers: dict[str, str], cfg):
    """根据配置确定使用哪些检索器
    【正经注释】按优先级查找检索器配置：headers.retrievers > headers.retriever > cfg.retrievers > cfg.retriever > 默认值。
    支持逗号分隔的多检索器配置。无效名称会回退到默认检索器。
    【大白话注释】看看要用哪些搜索引擎，按这个顺序找：
    1. 请求头里有没有指定多个？ 2. 请求头里有没有指定一个？
    3. 配置文件里有没有多个？ 4. 配置文件里有没有一个？
    5. 都没有就用默认的 Tavily
    Args:
        headers: HTTP 请求头字典（大白话：前端传来的请求头）
        cfg: 配置对象（大白话：配置信息）
    Returns:
        list: 检索器类列表（大白话：要用的搜索引擎清单）
    """
    # Check headers first for multiple retrievers			# 正经注释：优先级1 - 从请求头获取多个检索器 / 大白话注释：先看请求头里有没有指定多个搜索引擎
    if headers.get("retrievers"):
        retrievers = headers.get("retrievers").split(",")	# 正经注释：逗号分隔解析 / 大白话注释：用逗号切开
    # If not found, check headers for a single retriever	# 正经注释：优先级2 - 从请求头获取单个检索器 / 大白话注释：看看请求头里有没有指定一个
    elif headers.get("retriever"):
        retrievers = [headers.get("retriever")]				# 正经注释：单个包装为列表 / 大白话注释：放到列表里
    # If not in headers, check config for multiple retrievers	# 正经注释：优先级3 - 从配置获取多个检索器 / 大白话注释：再看配置文件里有没有多个
    elif cfg.retrievers:
        # Handle both list and string formats for config retrievers	# 正经注释：兼容列表和字符串两种格式 / 大白话注释：可能是逗号分隔的字符串，也可能是列表
        if isinstance(cfg.retrievers, str):
            retrievers = cfg.retrievers.split(",")			# 正经注释：字符串按逗号分割 / 大白话注释：字符串切开
        else:
            retrievers = cfg.retrievers						# 正经注释：直接使用列表 / 大白话注释：已经是列表就直接用
        # Strip whitespace from each retriever name		# 正经注释：去除每个名称的首尾空格 / 大白话注释：去掉多余空格
        retrievers = [r.strip() for r in retrievers]
    # If not found, check config for a single retriever	# 正经注释：优先级4 - 从配置获取单个检索器 / 大白话注释：配置文件里有没有指定一个
    elif cfg.retriever:
        retrievers = [cfg.retriever]						# 正经注释：单个包装为列表 / 大白话注释：放到列表里
    # If still not set, use default retriever				# 正经注释：优先级5 - 使用默认检索器 / 大白话注释：都没找到就用默认的
    else:
        retrievers = [get_default_retriever().__name__]		# 正经注释：使用默认检索器的类名 / 大白话注释：用默认搜索引擎的名字

    # Convert retriever names to actual retriever classes	# 正经注释：将检索器名称转换为实际的类对象 / 大白话注释：把名字变成真正的搜索引擎
    # Use get_default_retriever() as a fallback for any invalid retriever names	# 正经注释：无效名称回退到默认检索器 / 大白话注释：不认识的就用默认的
    retriever_classes = [get_retriever(r) or get_default_retriever() for r in retrievers]	# 正经注释：逐个转换，None 则用默认 / 大白话注释：一个一个找，找不到就用默认

    return retriever_classes								# 正经注释：返回检索器类列表 / 大白话注释：交出去


def get_default_retriever():
    """获取默认检索器类
    【正经注释】返回 TavilySearch 作为默认搜索提供商。
    【大白话注释】默认用 Tavily 搜索引擎。
    Returns:
        TavilySearch 检索器类（大白话：Tavily 搜索引擎）
    """
    from gpt_researcher.retrievers import TavilySearch		# 正经注释：延迟导入 TavilySearch / 大白话注释：用到了才导入

    return TavilySearch										# 正经注释：返回 TavilySearch 类 / 大白话注释：交出去