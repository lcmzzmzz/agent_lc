"""
Tavily 搜索引擎检索器。

【正经注释】本模块实现了基于Tavily API的网络搜索功能。
Tavily是专为AI代理设计的搜索引擎API，支持基础(basic)和高级(advanced)搜索深度，
支持域名过滤和主题分类搜索，返回标准化的搜索结果格式。

【大白话注释】这个文件是用来搜Tavily的。Tavily是一个专门给AI用的搜索引擎，
搜索结果比较干净，适合AI处理。你给它关键词，它就帮你搜网页，
搜完把链接和内容整理好给你。
"""

"""Tavily API search retriever for GPT Researcher.

This module provides the TavilySearch class for performing web searches
using the Tavily API.
"""

import json  # 正经注释：JSON解析库，用于序列化请求体和解析响应 / 大白话注释：处理JSON数据用的
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：读系统里存的API密钥
from typing import Literal, Optional, Sequence  # 正经注释：类型提示相关导入 / 大白话注释：类型标注用的

import requests  # 正经注释：HTTP请求库 / 大白话注释：发网络请求用的工具


class TavilySearch:
    """
    Tavily API 搜索引擎检索器。

    【正经注释】
    通过Tavily REST API实现的网页搜索类。
    支持基础(basic)和高级(advanced)搜索深度，支持域名过滤和主题分类。
    API密钥优先从headers参数获取，其次从环境变量TAVILY_API_KEY获取。

    【大白话注释】
    这个类就是帮你用Tavily搜东西的。Tavily是GPT Researcher的默认搜索引擎。
    可以从参数传密钥，也可以从环境变量读。

    需要设置的环境变量：
    - TAVILY_API_KEY: Tavily的API密钥
    """

    def __init__(self, query, headers=None, topic="general", query_domains=None):
        """
        初始化TavilySearch对象。

        【正经注释】
        接收搜索查询语句和可选参数，设置Tavily API的URL和认证信息。
        API密钥优先从headers中的tavily_api_key获取，其次从环境变量获取。

        【大白话注释】
        准备工作——记下要搜什么、搜什么主题、限定搜哪些网站，
        然后去找Tavily的钥匙。

        Args:
            query (str): 搜索查询关键词
            headers (dict, optional): 额外的请求头，可包含tavily_api_key
            topic (str, optional): 搜索主题，默认"general"
            query_domains (list, optional): 要限定搜索的域名列表
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.headers = headers or {}  # 正经注释：保存请求头字典 / 大白话注释：记住请求头
        self.topic = topic  # 正经注释：保存搜索主题 / 大白话注释：记住搜什么主题
        self.base_url = "https://api.tavily.com/search"  # 正经注释：Tavily搜索API端点 / 大白话注释：Tavily的搜索网址
        self.api_key = self.get_api_key()  # 正经注释：获取API密钥 / 大白话注释：去拿钥匙
        self.headers = {
            "Content-Type": "application/json",  # 正经注释：JSON内容类型 / 大白话注释：告诉服务器发JSON
        }
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站

    def get_api_key(self):
        """
        获取Tavily API密钥。

        【正经注释】
        优先从headers参数中的tavily_api_key获取密钥，
        其次从环境变量TAVILY_API_KEY获取，均不可用时返回空字符串。

        【大白话注释】
        去找Tavily的钥匙。先看参数里有没有，没有就去环境变量找。
        都找不到就返回空的，后面搜的时候会报错提示。

        Returns:
            str: Tavily API密钥

        """
        api_key = self.headers.get("tavily_api_key")  # 正经注释：从headers中获取API密钥 / 大白话注释：先看参数里有没有钥匙
        if not api_key:  # 正经注释：headers中无密钥时尝试从环境变量获取 / 大白话注释：参数里没有就去系统里找
            try:
                api_key = os.environ["TAVILY_API_KEY"]  # 正经注释：从环境变量读取API密钥 / 大白话注释：去系统里找钥匙
            except KeyError:  # 正经注释：环境变量中也没有时打印提示 / 大白话注释：系统里也没有就提醒你
                print(
                    "Tavily API key not found, set to blank. If you need a retriver, please set the TAVILY_API_KEY environment variable."
                )
                return ""  # 正经注释：返回空字符串 / 大白话注释：返回空的
        return api_key  # 正经注释：返回API密钥 / 大白话注释：把钥匙交出去


    def _search(
        self,
        query: str,
        search_depth: Literal["basic", "advanced"] = "basic",
        topic: str = "general",
        days: int = 2,
        max_results: int = 10,
        include_domains: Sequence[str] = None,
        exclude_domains: Sequence[str] = None,
        include_answer: bool = False,
        include_raw_content: bool = True,
        include_images: bool = False,
        use_cache: bool = True,
    ) -> dict:
        """
        内部搜索方法，发送请求到Tavily API。

        【正经注释】
        构建完整的搜索请求体并通过POST方式发送到Tavily API，
        支持搜索深度、时间范围、域名过滤、答案生成、原始内容获取等多种选项。

        【大白话注释】
        这是真正跟Tavily API通信的底层方法。把所有搜索参数打包成JSON发过去，
        把结果拿回来。

        Args:
            query: 搜索查询关键词
            search_depth: 搜索深度，"basic"或"advanced"
            topic: 搜索主题
            days: 搜索最近多少天的结果
            max_results: 最大返回结果数
            include_domains: 限定搜索的域名列表
            exclude_domains: 排除的域名列表
            include_answer: 是否包含AI生成的答案
            include_raw_content: 是否包含原始网页内容
            include_images: 是否包含图片
            use_cache: 是否使用缓存

        Returns:
            dict: Tavily API的响应字典
        """

        data = {
            "query": query,  # 正经注释：搜索查询语句 / 大白话注释：搜什么
            "search_depth": search_depth,  # 正经注释：搜索深度 / 大白话注释：搜多深
            "topic": topic,  # 正经注释：搜索主题 / 大白话注释：什么主题
            "days": days,  # 正经注释：搜索时间范围（天） / 大白话注释：最近几天的
            "include_answer": include_answer,  # 正经注释：是否包含AI答案 / 大白话注释：要不要AI总结
            "include_raw_content": include_raw_content,  # 正经注释：是否包含原始内容 / 大白话注释：要不要原文
            "max_results": max_results,  # 正经注释：最大结果数 / 大白话注释：要几条
            "include_domains": include_domains,  # 正经注释：限定搜索域名 / 大白话注释：只搜哪些网站
            "exclude_domains": exclude_domains,  # 正经注释：排除的域名 / 大白话注释：不搜哪些网站
            "include_images": include_images,  # 正经注释：是否包含图片 / 大白话注释：要不要图片
            "api_key": self.api_key,  # 正经注释：API密钥 / 大白话注释：钥匙
            "use_cache": use_cache,  # 正经注释：是否使用缓存 / 大白话注释：用不用缓存
        }

        response = requests.post(  # 正经注释：发送POST请求到Tavily API / 大白话注释：正式发搜索请求
            self.base_url, data=json.dumps(data), headers=self.headers, timeout=100
        )

        if response.status_code == 200:  # 正经注释：状态码200表示成功 / 大白话注释：请求成功了
            return response.json()  # 正经注释：返回解析后的JSON响应 / 大白话注释：把结果解析出来
        else:  # 正经注释：非200状态码时抛出HTTP错误 / 大白话注释：请求出问题了就报错
            # Raises a HTTPError if the HTTP request returned an unsuccessful status code
            response.raise_for_status()

    def search(self, max_results=10):
        """
        执行Tavily搜索查询。

        【正经注释】
        通过内部_search方法执行基础搜索，提取results字段中的URL和内容，
        转换为标准的{href, body}格式返回。异常时返回空列表。

        【大白话注释】
        去Tavily搜东西。搜完把每条结果的链接和内容整理好给你。
        出错了也不崩溃，返回空结果。

        Returns:
            list: 标准化的搜索结果列表

        """
        try:
            # Search the query
            results = self._search(  # 正经注释：调用内部搜索方法 / 大白话注释：去Tavily搜
                self.query,
                search_depth="basic",  # 正经注释：使用基础搜索深度 / 大白话注释：用基础模式搜
                max_results=max_results,
                topic=self.topic,  # 正经注释：使用初始化时指定的主题 / 大白话注释：用设好的主题
                include_domains=self.query_domains,  # 正经注释：传入/域名过滤列表 / 大白话注释：限定搜哪些网站
            )
            sources = results.get("results", [])  # 正经注释：提取搜索结果列表 / 大白话注释：把结果拿出来
            if not sources:  # 正经注释：结果为空时抛出异常 / 大白话注释：没搜到就报错
                raise Exception("No results found with Tavily API search.")
            # Return the results
            search_response = [
                {"href": obj["url"], "body": obj["content"]} for obj in sources  # 正经注释：将Tavily结果转换为标准{href, body}格式 / 大白话注释：整理成统一格式
            ]
        except Exception as e:  # 正经注释：捕获异常并返回空列表 / 大白话注释：出错了就记一下，返回空结果
            print(f"Error: {e}. Failed fetching sources. Resulting in empty response.")
            search_response = []
        return search_response  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去
