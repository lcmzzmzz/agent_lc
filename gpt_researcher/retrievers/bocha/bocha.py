"""
BoCha 搜索引擎检索器。

【正经注释】本模块实现了基于BoCha AI Web Search API的网络搜索功能，
通过博查搜索引擎获取网页搜索结果，支持时间范围过滤和长文本摘要，
返回标准化的搜索结果格式。

【大白话注释】这个文件是用来搜BoCha（博查）搜索引擎的。你给它关键词，
它就跑去博查的API帮你搜网页，搜到之后把标题、链接和摘要整理好给你。
博查是一个国内的AI搜索服务。
"""

# BoCha Search Retriever

# libraries
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来从系统里读API密钥
import requests  # 正经注释：HTTP请求库，用于调用BoCha搜索API / 大白话注释：发网络请求用的工具
import json  # 正经注释：JSON解析库 / 大白话注释：解析JSON数据用的
import logging  # 正经注释：日志记录模块 / 大白话注释：记日志用的


class BoChaSearch():
    """
    BoCha 搜索引擎检索器。

    【正经注释】
    通过BoCha AI Web Search API实现的网页搜索类。
    支持从环境变量自动获取API密钥，支持时间范围过滤和摘要生成，
    返回标准化的{title, href, body}搜索结果格式。

    【大白话注释】
    这个类就是帮你用博查搜索引擎搜东西的。给它关键词，它就去搜，
    搜完把结果整理好还给你。
    """

    def __init__(self, query, query_domains=None):
        """
        初始化BoChaSearch对象。

        【正经注释】
        构造函数，接收搜索查询语句，从环境变量加载BoCha API密钥。

        【大白话注释】
        准备工作——记下你要搜什么，然后去找博查的钥匙（API密钥）。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站
        self.api_key = os.environ["BOCHA_API_KEY"]  # 正经注释：从环境变量获取BoCha API密钥 / 大白话注释：去系统里拿博查的钥匙

    def search(self, max_results=7) -> list[dict[str]]:
        """
        执行BoCha搜索查询。

        【正经注释】
        通过BoCha Web Search API执行搜索，支持时间范围和摘要选项，
        返回标准化的搜索结果列表。

        【大白话注释】
        真正去博查搜索引擎搜东西。搜完把结果整理成统一格式给你。

        Returns:
            list[dict[str]]: 标准化的搜索结果列表

        """
        url = 'https://api.bochaai.com/v1/web-search'  # 正经注释：BoCha Web Search API端点地址 / 大白话注释：博查搜索的网址
        headers = {
            'Authorization': f'Bearer {self.api_key}',  # 正经注释：Bearer Token认证头 / 大白话注释：把API钥匙放在请求头里
            'Content-Type': 'application/json'  # 正经注释：指定请求内容类型为JSON / 大白话注释：告诉服务器我要发JSON数据
        }
        data = {
            "query": self.query,  # 正经注释：搜索查询语句 / 大白话注释：要搜什么关键词
            "freshness": "noLimit",  # 正经注释：搜索时间范围，noLimit表示不限制时间 / 大白话注释：不限时间范围，啥时候的都要
            "summary": True,  # 正经注释：是否返回长文本摘要 / 大白话注释：让博查帮忙总结一下内容
            "count": max_results  # 正经注释：返回结果数量 / 大白话注释：要几条结果
        }

        response = requests.post(url, headers=headers, json=data)  # 正经注释：发送POST请求到BoCha API / 大白话注释：正式向博查发搜索请求

        json_response = response.json()  # 正经注释：解析API返回的JSON响应 / 大白话注释：把博查返回的数据解析出来
        results = json_response["data"]["webPages"]["value"]  # 正经注释：提取网页搜索结果列表 / 大白话注释：从返回数据里把网页结果拿出来
        search_results = []  # 正经注释：初始化标准化结果列表 / 大白话注释：准备一个空箱子装整理好的结果

        # Normalize the results to match the format of the other search APIs
        for result in results:  # 正经注释：遍历原始搜索结果并转换格式 / 大白话注释：一条一条地整理搜到的结果
            search_result = {
                "title": result["name"],  # 正经注释：网页标题 / 大白话注释：网页叫啥
                "href": result["url"],  # 正经注释：网页URL / 大白话注释：网页链接
                "body": result["snippet"],  # 正经注释：网页摘要片段 / 大白话注释：网页简介
            }
            search_results.append(search_result)  # 正经注释：添加到结果列表 / 大白话注释：放进箱子里

        return search_results  # 正经注释：返回标准化搜索结果 / 大白话注释：把整理好的结果交出去
