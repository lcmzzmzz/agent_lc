"""
SerpApi 搜索引擎检索器。

【正经注释】本模块实现了基于SerpApi的网络搜索功能。
SerpApi是一个提供结构化搜索引擎结果的API服务，
支持Google等搜索引擎的结果解析，支持域名过滤，返回标准化的搜索结果格式。

【大白话注释】这个文件是用来搜SerpApi的。SerpApi能帮你把Google搜索结果结构化地拿回来。
你给它关键词，它就帮你搜，搜完把标题、链接和摘要整理好给你。
YouTube的结果会被自动跳过。还支持限定只搜某些网站。
"""

# SerpApi Retriever

# libraries
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读系统里存的API密钥
import requests  # 正经注释：HTTP请求库 / 大白话注释：发网络请求用的工具
import urllib.parse  # 正经注释：URL编码工具 / 大白话注释：拼网址参数用的


class SerpApiSearch():
    """
    SerpApi 搜索引擎检索器。

    【正经注释】
    通过SerpApi REST API实现的网页搜索类。
    支持通过site:语法限定搜索域名范围，自动排除YouTube结果。

    【大白话注释】
    这个类就是帮你用SerpApi搜东西的。可以限定只搜某些网站。
    YouTube的结果会被自动丢掉。

    需要设置的环境变量：
    - SERPAPI_API_KEY: SerpApi的API密钥
    """

    def __init__(self, query, query_domains=None):
        """
        初始化SerpApiSearch对象。

        【正经注释】
        接收搜索查询语句和可选的域名过滤列表，从环境变量加载API密钥。

        【大白话注释】
        准备工作——记下要搜什么和要限定搜哪些网站，去找SerpApi的钥匙。

        Args:
            query: 搜索查询关键词
            query_domains: 要限定搜索的域名列表
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站
        self.api_key = self.get_api_key()  # 正经注释：获取API密钥 / 大白话注释：去拿钥匙

    def get_api_key(self):
        """
        从环境变量获取SerpApi API密钥。

        【正经注释】
        从系统环境变量中读取SERPAPI_API_KEY，
        若未设置则抛出异常并提供获取指引。

        【大白话注释】
        去系统里找SerpApi的钥匙。找不到就告诉你去哪申请。

        Returns:
            str: SerpApi API密钥

        """
        try:
            api_key = os.environ["SERPAPI_API_KEY"]  # 正经注释：从环境变量读取API密钥 / 大白话注释：去系统里找钥匙
        except Exception:  # 正经注释：密钥不存在时抛出友好错误 / 大白话注释：没找到钥匙就报错
            raise Exception("SerpApi API key not found. Please set the SERPAPI_API_KEY environment variable. "
                            "You can get a key at https://serpapi.com/")
        return api_key  # 正经注释：返回API密钥 / 大白话注释：把钥匙交出去

    def search(self, max_results=7):
        """
        执行SerpApi搜索查询。

        【正经注释】
        通过SerpApi API执行搜索，支持通过site:语法限定域名范围，
        解析organic_results字段，自动排除YouTube结果。

        【大白话注释】
        真正去SerpApi搜东西。可以限定搜哪些网站。YouTube的链接会被自动跳过。

        Returns:
            list: 标准化的搜索结果列表

        """
        print("SerpApiSearch: Searching with query {0}...".format(self.query))  # 正经注释：输出搜索日志 / 大白话注释：打印正在搜什么
        """Useful for general internet search queries using SerpApi."""

        url = "https://serpapi.com/search.json"  # 正经注释：SerpApi搜索端点 / 大白话注释：SerpApi的搜索网址

        search_query = self.query  # 正经注释：初始化搜索查询语句 / 大白话注释：先拿原始关键词
        if self.query_domains:  # 正经注释：如果设置了域名过滤则添加site:限定 / 大白话注释：要限定搜某些网站就加上条件
            # Add site:domain1 OR site:domain2 OR ... to the search query
            search_query += " site:" + " OR site:".join(self.query_domains)  # 正经注释：用OR连接多个site:限定符 / 大白话注释：把多个网站用"或者"连起来

        params = {
            "q": search_query,  # 正经注释：搜索查询参数 / 大白话注释：搜什么
            "api_key": self.api_key  # 正经注释：API密钥认证 / 大白话注释：钥匙
        }
        encoded_url = url + "?" + urllib.parse.urlencode(params)  # 正经注释：构建带参数的完整URL / 大白话注释：把参数拼到网址后面
        search_response = []  # 正经注释：初始化结果列表 / 大白话注释：准备空箱子
        try:
            response = requests.get(encoded_url, timeout=10)  # 正经注释：发送GET请求，10秒超时 / 大白话注释：正式发搜索请求
            if response.status_code == 200:  # 正经注释：状态码200表示成功 / 大白话注释：请求成功了
                search_results = response.json()  # 正经注释：解析JSON响应 / 大白话注释：把数据解析出来
                if search_results:  # 正经注释：验证结果非空 / 大白话注释：有结果才继续
                    results = search_results["organic_results"]  # 正经注释：提取自然搜索结果 / 大白话注释：把搜索结果拿出来
                    results_processed = 0  # 正经注释：已处理计数器 / 大白话注释：数一数处理了几条
                    for result in results:  # 正经注释：遍历搜索结果 / 大白话注释：一条一条看
                        # skip youtube results
                        if "youtube.com" in result["link"]:  # 正经注释：跳过YouTube链接 / 大白话注释：YouTube的不要
                            continue
                        if results_processed >= max_results:  # 正经注释：达到最大结果数时停止 / 大白话注释：够了就不找了
                            break
                        search_result = {
                            "title": result["title"],  # 正经注释：结果标题 / 大白话注释：叫什么
                            "href": result["link"],  # 正经注释：结果URL / 大白话注释：链接
                            "body": result["snippet"],  # 正经注释：结果摘要 / 大白话注释：简介
                        }
                        search_response.append(search_result)  # 正经注释：添加到结果列表 / 大白话注释：放进箱子里
                        results_processed += 1  # 正经注释：递增计数器 / 大白话注释：又多了一条
        except Exception as e:  # 正经注释：捕获所有异常 / 大白话注释：出错了就记一下
            print(f"Error: {e}. Failed fetching sources. Resulting in empty response.")
            search_response = []

        return search_response  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去
