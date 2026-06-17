"""
GPT Researcher 检索器（Retriever）总包。

【正经注释】本模块为所有搜索引擎/数据源检索器的统一入口，通过集中导入和导出
各个子模块的检索器类，实现统一的检索器注册与管理机制。上层代码可直接从本模块
导入所需的检索器类。

【大白话注释】这就是所有搜索器的"大总管"。不管你想用Google、Bing、DuckDuckGo
还是Arxiv这些搜索引擎，都得从这个门口进来拿。这个文件把下面每个子文件夹里的
搜索类全都汇总在一起，方便外面一句话就import到。
"""

from .arxiv.arxiv import ArxivSearch  # 正经注释：导入Arxiv学术论文检索器 / 大白话注释：把Arxiv搜索器拿上来
from .bing.bing import BingSearch  # 正经注释：导入Bing搜索引擎检索器 / 大白话注释：把Bing搜索器拿上来
from .custom.custom import CustomRetriever  # 正经注释：导入自定义API检索器 / 大白话注释：把自定义搜索器拿上来
from .duckduckgo.duckduckgo import Duckduckgo  # 正经注释：导入DuckDuckGo搜索引擎检索器 / 大白话注释：把DuckDuckGo搜索器拿上来
from .google.google import GoogleSearch  # 正经注释：导入Google自定义搜索检索器 / 大白话注释：把Google搜索器拿上来
from .pubmed_central.pubmed_central import PubMedCentralSearch  # 正经注释：导入PubMed Central生物医学文献检索器 / 大白话注释：把PubMed搜索器拿上来
from .searx.searx import SearxSearch  # 正经注释：导入SearxNG元搜索引擎检索器 / 大白话注释：把Searx搜索器拿上来
from .semantic_scholar.semantic_scholar import SemanticScholarSearch  # 正经注释：导入Semantic Scholar学术搜索检索器 / 大白话注释：把Semantic Scholar搜索器拿上来
from .searchapi.searchapi import SearchApiSearch  # 正经注释：导入SearchApi检索器 / 大白话注释：把SearchApi搜索器拿上来
from .serpapi.serpapi import SerpApiSearch  # 正经注释：导入SerpApi检索器 / 大白话注释：把SerpApi搜索器拿上来
from .serper.serper import SerperSearch  # 正经注释：导入Serper（Google Serper）检索器 / 大白话注释：把Serper搜索器拿上来
from .tavily.tavily_search import TavilySearch  # 正经注释：导入Tavily搜索检索器 / 大白话注释：把Tavily搜索器拿上来
from .exa.exa import ExaSearch  # 正经注释：导入Exa AI搜索引擎检索器 / 大白话注释：把Exa搜索器拿上来
from .mcp import MCPRetriever  # 正经注释：导入MCP协议检索器 / 大白话注释：把MCP搜索器拿上来
from .bocha.bocha import BoChaSearch  # 正经注释：导入BoCha搜索引擎检索器 / 大白话注释：把BoCha搜索器拿上来
from .xquik.xquik import XquikSearch  # 正经注释：导入Xquik X/Twitter社交媒体检索器 / 大白话注释：把Xquik推特搜索器拿上来
from .openalex.openalex import OpenAlexSearch  # 正经注释：导入OpenAlex学术文献检索器 / 大白话注释：把OpenAlex搜索器拿上来

__all__ = [  # 正经注释：定义本模块对外暴露的公开API列表 / 大白话注释：告诉Python"这些类都是可以对外卖的"
    "TavilySearch",
    "CustomRetriever",
    "Duckduckgo",
    "SearchApiSearch",
    "SerperSearch",
    "SerpApiSearch",
    "GoogleSearch",
    "SearxSearch",
    "BingSearch",
    "ArxivSearch",
    "SemanticScholarSearch",
    "PubMedCentralSearch",
    "ExaSearch",
    "MCPRetriever",
    "BoChaSearch",
    "XquikSearch",
    "OpenAlexSearch"
]
