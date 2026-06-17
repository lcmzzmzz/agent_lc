"""
SearchApi 搜索引擎检索器。

【正经注释】本模块实现了基于SearchApi API的网络搜索功能，
通过SearchApi聚合Google等搜索引擎的结果，返回标准化的搜索结果格式。

【大白话注释】这个文件是用来搜SearchApi的。SearchApi是一个搜索聚合服务，
它能帮你搜Google等搜索引擎的结果。你给它关键词，它就帮你搜，
搜完把标题、链接和摘要整理好给你。YouTube的结果会被自动跳过。
"""

# SearchApi Retriever

# libraries
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读系统里存的API密钥
import requests  # 正经注释：HTTP请求库，用于调用SearchApi / 大白话注释：发网络请求用的工具
import urllib.parse  # 正经注释：URL编码工具，用于构建查询参数 / 大白话注释：拼网址参数用的


class SearchApiSearch():
    """
    SearchApi 搜索引擎检索器。

    【正经注释】
    通过SearchApi REST API实现的网页搜索类。
    默认使用Google引擎，支持Bearer Token认证，
    自动排除YouTube结果。

    【大白话注释】
    这个类就是帮你用SearchApi搜东西的。默认用Google引擎搜。
    YouTube的结果会被自动丢掉。

    需要设置的环境变量：
    - SEARCHAPI_API_KEY: SearchApi的API密钥
    """

    def __init__(self, query, query_domains=None):
        """
        初始化SearchApiSearch对象。

        【正经注释】
        接收搜索查询语句，从环境变量加载SearchApi API密钥。

        【大白话注释】
        准备工作——记下要搜什么，去找SearchApi的钥匙。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表（当前版本未实现）
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.api_key = self.get_api_key()  # 正经注释：获取API密钥 / 大白话注释：去拿钥匙

    def get_api_key(self):
        """
        从环境变量获取SearchApi API密钥。

        【正经注释】
        从系统环境变量中读取SEARCHAPI_API_KEY，
        若未设置则抛出异常并提供获取指引。

        【大白话注释】
        去系统里找SearchApi的钥匙。找不到就告诉你去哪申请。

        Returns:
            str: SearchApi API密钥

        """
        try:
            api_key = os.environ["SEARCHAPI_API_KEY"]  # 正经注释：从环境变量读取API密钥 / 大白话注释：去系统里找钥匙
        except Exception:  # 正经注释：密钥不存在时抛出友好错误 / 大白话注释：没找到钥匙就报错
            raise Exception("SearchApi key not found. Please set the SEARCHAPI_API_KEY environment variable. "
                            "You can get a key at https://www.searchapi.io/")
        return api_key  # 正经注释：返回API密钥 / 大白话注释：把钥匙交出去

    def search(self, max_results=7):
        """
        执行SearchApi搜索查询。

        【正经注释】
        通过SearchApi API执行Google搜索，解析organic_results字段，
        自动排除YouTube结果，返回标准化的搜索结果列表。

        【大白话注释】
        真正去SearchApi搜东西。默认用Google引擎。YouTube的链接会被自动跳过。

        Returns:
            list: 标准化的搜索结果列表

        """
        print("SearchApiSearch: Searching with query {0}...".format(self.query))  # 正经注释：输出搜索日志 / 大白话注释：打印正在搜什么
        """Useful for general internet search queries using SearchApi."""


        url = "https://www.searchapi.io/api/v1/search"  # 正经注释：SearchApi搜索端点 / 大白话注释：SearchApi的搜索网址
        params = {
            "q": self.query,  # 正经注释：搜索查询参数 / 大白话注释：搜什么关键词
            "engine": "google",  # 正经注释：使用Google搜索引擎 / 大白话注释：用Google来搜
        }

        headers = {
            'Content-Type': 'application/json',  # 正经注释：JSON内容类型 / 大白话注释：告诉服务器发JSON
            'Authorization': f'Bearer {self.api_key}',  # 正经注释：Bearer Token认证 / 大白话注释：带上钥匙
            'X-SearchApi-Source': 'gpt-researcher'  # 正经注释：标识请求来源 / 大白话注释：告诉对方"我是GPT Researcher"
        }

        encoded_url = url + "?" + urllib.parse.urlencode(params)  # 正经注释：构建带查询参数的完整URL / 大白话注释：把参数拼到网址后面
        search_response = []  # 正经注释：初始化结果列表 / 大白话注释：准备空箱子

        try:
            response = requests.get(encoded_url, headers=headers, timeout=20)  # 正经注释：发送GET请求，20秒超时 / 大白话注释：正式发搜索请求
            if response.status_code == 200:  # 正经注释：状态码200表示请求成功 / 大白话注释：请求成功了
                search_results = response.json()  # 正经注释：解析JSON响应 / 大白话注释：把返回数据解析出来
                if search_results:  # 正经注释：验证搜索结果非空 / 大白话注释：有结果才继续
                    results = search_results["organic_results"]  # 正经注释：提取自然搜索结果 / 大白话注释：把搜索结果拿出来
                    results_processed = 0  # 正经注释：已处理结果计数器 / 大白话注释：数一数处理了几条
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
                        results_processed += 1  # 正经注释：递增计数器 / 大白话注释：又多处理了一条
        except Exception as e:  # 正经注释：捕获所有异常 / 大白话注释：出错了就记一下
            print(f"Error: {e}. Failed fetching sources. Resulting in empty response.")
            search_response = []

        return search_response  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去
