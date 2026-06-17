"""
Bing 搜索引擎检索器。

【正经注释】本模块实现了基于Bing Web Search API的网络搜索功能，
通过Microsoft Bing搜索引擎获取网页搜索结果，并自动过滤YouTube链接，
返回标准化的搜索结果格式。

【大白话注释】这个文件是用来搜Bing的。你给它关键词，它就去Bing搜索引擎
帮你搜网页，搜到之后把标题、链接和摘要整理好给你。YouTube的结果会被自动跳过。
"""

# Bing Search Retriever

# libraries
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读取系统里存的东西，比如API密钥
import requests  # 正经注释：HTTP请求库，用于调用Bing搜索API / 大白话注释：用来发网络请求的工具
import json  # 正经注释：JSON解析库，用于处理API返回的JSON数据 / 大白话注释：解析JSON数据用的
import logging  # 正经注释：日志记录模块 / 大白话注释：记日志用的


class BingSearch():
    """
    Bing 搜索引擎检索器。

    【正经注释】
    通过Microsoft Bing Web Search API v7实现的网页搜索类。
    支持从环境变量自动获取API密钥，自动过滤YouTube结果，
    返回标准化的{title, href, body}搜索结果格式。

    【大白话注释】
    这个类就是帮你用Bing搜东西的。它会去Bing的API问一圈，
    把搜到的网页信息整理好还给你。YouTube的结果会被自动丢掉。
    """

    def __init__(self, query, query_domains=None):
        """
        初始化BingSearch对象。

        【正经注释】
        构造函数，接收搜索查询语句，从环境变量加载Bing API密钥，
        并初始化日志记录器。

        【大白话注释】
        准备工作——记下你要搜什么，然后去找Bing的钥匙（API密钥）。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表（当前版本未实现）
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站（目前还没实现这个功能）
        self.api_key = self.get_api_key()  # 正经注释：从环境变量获取API密钥 / 大白话注释：去拿Bing的钥匙
        self.logger = logging.getLogger(__name__)  # 正经注释：初始化当前模块的日志记录器 / 大白话注释：搞个日志记录器

    def get_api_key(self):
        """
        从环境变量获取Bing API密钥。

        【正经注释】
        从系统环境变量中读取BING_API_KEY，若未设置则抛出异常提示用户配置。

        【大白话注释】
        去系统里找Bing的API钥匙。找不到就告诉你"没设密码，请先设一个"。

        Returns:
            str: Bing API密钥

        """
        try:
            api_key = os.environ["BING_API_KEY"]  # 正经注释：从环境变量读取Bing API密钥 / 大白话注释：去系统里找Bing的钥匙
        except Exception:  # 正经注释：密钥不存在时抛出友好错误提示 / 大白话注释：没找到钥匙就报错告诉你
            raise Exception(
                "Bing API key not found. Please set the BING_API_KEY environment variable.")
        return api_key  # 正经注释：返回获取到的API密钥 / 大白话注释：把钥匙交出去

    def search(self, max_results=7) -> list[dict[str]]:
        """
        执行Bing搜索查询。

        【正经注释】
        通过Bing Web Search API v7执行搜索，应用安全搜索和响应过滤，
        自动排除YouTube结果，返回标准化的搜索结果列表。

        【大白话注释】
        真正去Bing搜东西。把搜到的网页整理成统一格式给你。
        YouTube的链接会被自动跳过不返回。

        Returns:
            list[dict[str]]: 标准化的搜索结果列表

        """
        print("Searching with query {0}...".format(self.query))  # 正经注释：输出搜索开始日志 / 大白话注释：打印一下正在搜什么
        """Useful for general internet search queries using the Bing API."""

        # Search the query
        url = "https://api.bing.microsoft.com/v7.0/search"  # 正经注释：Bing Web Search API端点地址 / 大白话注释：Bing搜索的网址

        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,  # 正经注释：Microsoft Azure订阅密钥认证头 / 大白话注释：把API钥匙放在请求头里
            'Content-Type': 'application/json'  # 正经注释：指定请求内容类型为JSON / 大白话注释：告诉服务器我要发JSON数据
        }
        # TODO: Add support for query domains  # 正经注释：待办：添加域名过滤支持 / 大白话注释：以后要加的功能——限定搜哪些网站
        params = {
            "responseFilter": "Webpages",  # 正经注释：仅返回网页类型结果 / 大白话注释：只要网页结果，不要图片视频那些
            "q": self.query,  # 正经注释：搜索查询参数 / 大白话注释：搜什么关键词
            "count": max_results,  # 正经注释：返回结果数量限制 / 大白话注释：要几条结果
            "setLang": "en-GB",  # 正经注释：设置界面语言为英式英语 / 大白话注释：语言设成英式英语
            "textDecorations": False,  # 正经注释：禁用文本装饰标记 / 大白话注释：不要那些花里胡哨的文本格式
            "textFormat": "HTML",  # 正经注释：文本格式设为HTML / 大白话注释：文本用HTML格式返回
            "safeSearch": "Strict"  # 正经注释：启用严格安全搜索模式 / 大白话注释：开启安全搜索，过滤不良内容
        }

        resp = requests.get(url, headers=headers, params=params)  # 正经注释：发送GET请求到Bing API / 大白话注释：正式向Bing发搜索请求

        # Preprocess the results
        if resp is None:  # 正经注释：响应为空时直接返回空列表 / 大白话注释：Bing没回应就返回空的
            return []
        try:
            search_results = json.loads(resp.text)  # 正经注释：解析API返回的JSON响应体 / 大白话注释：把Bing返回的JSON数据解析出来
            results = search_results["webPages"]["value"]  # 正经注释：提取网页搜索结果列表 / 大白话注释：从返回数据里把网页结果拿出来
        except Exception as e:  # 正经注释：JSON解析失败时记录错误并返回空列表 / 大白话注释：解析出错了就记个日志，返回空结果
            self.logger.error(
                f"Error parsing Bing search results: {e}. Resulting in empty response.")
            return []
        if search_results is None:  # 正经注释：搜索结果为空时记录警告 / 大白话注释：搜索结果为空就给个警告
            self.logger.warning(f"No search results found for query: {self.query}")
            return []
        search_results = []  # 正经注释：重新初始化结果列表用于存放标准化结果 / 大白话注释：清空箱子准备装整理好的结果

        # Normalize the results to match the format of the other search APIs
        for result in results:  # 正经注释：遍历原始搜索结果 / 大白话注释：一条一条地看搜到的结果
            # skip youtube results
            if "youtube.com" in result["url"]:  # 正经注释：过滤掉YouTube链接 / 大白话注释：YouTube的不要
                continue
            search_result = {
                "title": result["name"],  # 正经注释：网页标题 / 大白话注释：网页叫啥
                "href": result["url"],  # 正经注释：网页URL / 大白话注释：网页链接
                "body": result["snippet"],  # 正经注释：网页摘要片段 / 大白话注释：网页简介
            }
            search_results.append(search_result)  # 正经注释：添加到标准化结果列表 / 大白话注释：把这条结果放进箱子里

        return search_results  # 正经注释：返回标准化搜索结果列表 / 大白话注释：把整理好的全部结果交出去
