"""
Google 自定义搜索引擎检索器。

【正经注释】本模块实现了基于Google Custom Search API的网络搜索功能，
支持按域名过滤搜索范围，自动排除YouTube链接，
返回标准化的搜索结果格式。

【大白话注释】这个文件是用来搜Google的。它用的是Google的自定义搜索API，
不是普通的Google搜索。你给它关键词，它就跑去Google帮你搜网页，
搜到之后把标题、链接和摘要整理好给你。YouTube的结果会被自动跳过。
"""

# Tavily API Retriever

# libraries
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读系统里存的API密钥
import requests  # 正经注释：HTTP请求库，用于调用Google搜索API / 大白话注释：发网络请求用的工具
import json  # 正经注释：JSON解析库 / 大白话注释：解析JSON数据用的


class GoogleSearch:
    """
    Google 自定义搜索引擎检索器。

    【正经注释】
    通过Google Custom Search JSON API实现的网页搜索类。
    支持通过headers传入或从环境变量获取API密钥和CX密钥，
    支持按域名过滤搜索范围，自动排除YouTube结果。

    【大白话注释】
    这个类就是帮你用Google搜东西的。需要两个密钥：API密钥和CX密钥（自定义搜索引擎ID）。
    可以限定只搜某些网站，YouTube的结果会被自动丢掉。

    需要的环境变量：
    - GOOGLE_API_KEY: Google API密钥
    - GOOGLE_CX_KEY: Google自定义搜索引擎ID
    """

    def __init__(self, query, headers=None, query_domains=None):
        """
        初始化GoogleSearch对象。

        【正经注释】
        构造函数，接收搜索查询语句和可选的headers参数。
        API密钥和CX密钥优先从headers获取，其次从环境变量获取。

        【大白话注释】
        准备工作——记下要搜的关键词，然后去拿Google的两把钥匙。
        钥匙可以从参数传进来，也可以从环境变量里读。

        Args:
            query: 搜索查询关键词
            headers: 可选的请求头字典，可包含google_api_key和google_cx_key
            query_domains: 要限定搜索的域名列表
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.headers = headers or {}  # 正经注释：保存请求头字典 / 大白话注释：记住可能传进来的密钥
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站
        self.api_key = self.headers.get("google_api_key") or self.get_api_key()  # Use the passed api_key or fallback to environment variable  # 正经注释：优先从headers获取API密钥，否则从环境变量获取 / 大白话注释：先看参数里有没有钥匙，没有就去环境变量找
        self.cx_key = self.headers.get("google_cx_key") or self.get_cx_key()  # Use the passed cx_key or fallback to environment variable  # 正经注释：优先从headers获取CX密钥，否则从环境变量获取 / 大白话注释：先看参数里有没有CX钥匙，没有就去环境变量找

    def get_api_key(self):
        """
        从环境变量获取Google API密钥。

        【正经注释】
        从系统环境变量中读取GOOGLE_API_KEY，
        若未设置则抛出异常并提供获取密钥的URL指引。

        【大白话注释】
        去系统里找Google的API钥匙。找不到就告诉你去哪申请。

        Returns:
            str: Google API密钥

        """
        # Get the API key
        try:
            api_key = os.environ["GOOGLE_API_KEY"]  # 正经注释：从环境变量读取Google API密钥 / 大白话注释：去系统里找Google钥匙
        except Exception:  # 正经注释：密钥不存在时抛出友好错误 / 大白话注释：没找到钥匙就报错
            raise Exception("Google API key not found. Please set the GOOGLE_API_KEY environment variable. "
                            "You can get a key at https://developers.google.com/custom-search/v1/overview")
        return api_key  # 正经注释：返回API密钥 / 大白话注释：把钥匙交出去

    def get_cx_key(self):
        """
        从环境变量获取Google CX密钥（自定义搜索引擎ID）。

        【正经注释】
        从系统环境变量中读取GOOGLE_CX_KEY（自定义搜索引擎ID），
        若未设置则抛出异常并提供获取指引。

        【大白话注释】
        去系统里找Google的CX钥匙（自定义搜索引擎ID）。
        找不到就告诉你去哪申请。

        Returns:
            str: Google CX密钥

        """
        # Get the API key
        try:
            api_key = os.environ["GOOGLE_CX_KEY"]  # 正经注释：从环境变量读取Google CX密钥 / 大白话注释：去系统里找CX钥匙
        except Exception:  # 正经注释：CX密钥不存在时抛出友好错误 / 大白话注释：没找到就报错
            raise Exception("Google CX key not found. Please set the GOOGLE_CX_KEY environment variable. "
                            "You can get a key at https://developers.google.com/custom-search/v1/overview")
        return api_key  # 正经注释：返回CX密钥 / 大白话注释：把CX钥匙交出去

    def search(self, max_results=7):
        """
        执行Google自定义搜索。

        【正经注释】
        通过Google Custom Search API执行搜索查询，支持按指定域名范围过滤，
        自动排除YouTube结果，返回标准化的搜索结果列表。

        【大白话注释】
        真正去Google搜东西。如果设了域名过滤，就只搜那些网站。
        YouTube的链接会被自动跳过。

        Returns:
            list: 标准化的搜索结果列表，包含title、href和body
        """
        # Build query with domain restrictions if specified
        search_query = self.query  # 正经注释：初始化搜索查询语句 / 大白话注释：先拿原始关键词
        if self.query_domains and len(self.query_domains) > 0:  # 正经注释：如果设置了域名过滤则构建site限定查询 / 大白话注释：如果要限定搜某些网站就加上限定条件
            domain_query = " OR ".join([f"site:{domain}" for domain in self.query_domains])  # 正经注释：用OR连接多个site:限定符 / 大白话注释：用"或者"把多个网站连起来
            search_query = f"({domain_query}) {self.query}"  # 正经注释：组合域名限定和原始查询 / 大白话注释：把限定条件和关键词拼在一起

        print("Searching with query {0}...".format(search_query))  # 正经注释：输出搜索日志 / 大白话注释：打印正在搜什么

        url = f"https://www.googleapis.com/customsearch/v1?key={self.api_key}&cx={self.cx_key}&q={search_query}&start=1"  # 正经注释：构建Google Custom Search API请求URL / 大白话注释：拼出完整的Google搜索网址
        resp = requests.get(url)  # 正经注释：发送GET请求 / 大白话注释：正式向Google发搜索请求

        if resp.status_code < 200 or resp.status_code >= 300:  # 正经注释：检查HTTP状态码是否异常 / 大白话注释：看看请求有没有出问题
            print("Google search: unexpected response status: ", resp.status_code)

        if resp is None:  # 正经注释：响应为空时返回 / 大白话注释：Google没回应就直接返回
            return
        try:
            search_results = json.loads(resp.text)  # 正经注释：解析JSON响应 / 大白话注释：把Google返回的数据解析出来
        except Exception:  # 正经注释：JSON解析失败时返回 / 大白话注释：解析出错了就返回
            return
        if search_results is None:  # 正经注释：搜索结果为空时返回 / 大白话注释：结果为空就返回
            return

        results = search_results.get("items", [])  # 正经注释：从响应中提取搜索结果项 / 大白话注释：把搜到的条目拿出来
        search_results = []  # 正经注释：重新初始化结果列表 / 大白话注释：准备空箱子装整理好的结果

        # Normalizing results to match the format of the other search APIs
        for result in results:  # 正经注释：遍历并标准化每个搜索结果 / 大白话注释：一条一条地整理搜到的结果
            # skip youtube results
            if "youtube.com" in result["link"]:  # 正经注释：过滤掉YouTube链接 / 大白话注释：YouTube的不要
                continue
            try:
                search_result = {
                    "title": result["title"],  # 正经注释：网页标题 / 大白话注释：网页叫啥
                    "href": result["link"],  # 正经注释：网页URL / 大白话注释：网页链接
                    "body": result["snippet"],  # 正经注释：网页摘要片段 / 大白话注释：网页简介
                }
            except Exception:  # 正经注释：单条结果解析失败时跳过 / 大白话注释：这条有问题就跳过
                continue
            search_results.append(search_result)  # 正经注释：添加到结果列表 / 大白话注释：放进箱子里

        return search_results[:max_results]  # 正经注释：截取指定数量的结果返回 / 大白话注释：最多返回要的条数，把整理好的结果交出去
