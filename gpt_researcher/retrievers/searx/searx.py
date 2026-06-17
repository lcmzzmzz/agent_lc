"""
SearxNG 元搜索引擎检索器。

【正经注释】本模块实现了基于SearxNG API的元搜索功能。
SearxNG是一个开源的元搜索引擎，可以聚合Google、Bing等多个搜索引擎的结果。
通过自建或公共的SearxNG实例提供搜索服务，注重隐私保护。

【大白话注释】这个文件是用来搜SearxNG的。SearxNG是一个开源的"搜索引擎聚合器"，
它可以同时帮你搜Google、Bing等多个搜索引擎，然后把结果合在一起给你。
因为它是开源的，你可以自己搭一个，也可以用公共的实例。
"""

import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读系统里存的配置
import json  # 正经注释：JSON解析库 / 大白话注释：解析JSON数据用的
import requests  # 正经注释：HTTP请求库 / 大白话注释：发网络请求用的工具
from typing import List, Dict  # 正经注释：类型提示相关导入 / 大白话注释：类型标注用的
from urllib.parse import urljoin  # 正经注释：URL拼接工具，用于构建完整的搜索URL / 大白话注释：拼网址用的


class SearxSearch():
    """
    SearxNG 元搜索引擎检索器。

    【正经注释】
    通过SearxNG JSON API实现的元搜索类。SearxNG聚合多个搜索引擎的结果，
    支持自建实例和公共实例。需要在环境变量中配置SearxNG实例的URL。

    【大白话注释】
    这个类就是帮你用SearxNG搜东西的。SearxNG是个开源的搜索聚合器，
    一次帮你搜多个搜索引擎。需要你先配好SearxNG的网址。

    需要设置的环境变量：
    - SEARX_URL: SearxNG实例的URL地址
    """

    def __init__(self, query: str, query_domains=None):
        """
        初始化SearxSearch对象。

        【正经注释】
        接收搜索查询语句，从环境变量加载SearxNG实例URL。

        【大白话注释】
        准备工作——记下要搜什么，去找SearxNG的网址。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表（当前版本未实现）
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站
        self.base_url = self.get_searxng_url()  # 正经注释：获取SearxNG实例URL / 大白话注释：去找SearxNG的网址

    def get_searxng_url(self) -> str:
        """
        从环境变量获取SearxNG实例URL。

        【正经注释】
        从系统环境变量中读取SEARX_URL，自动确保URL以斜杠结尾，
        若未设置则抛出异常并提供公共实例列表指引。

        【大白话注释】
        去系统里找SearxNG的网址。找不到就告诉你去哪找公共的SearxNG实例。

        Returns:
            str: SearxNG实例的基础URL

        Raises:
            Exception: 环境变量未设置时抛出
        """
        try:
            base_url = os.environ["SEARX_URL"]  # 正经注释：从环境变量读取SearxNG URL / 大白话注释：去系统里找SearxNG的网址
            if not base_url.endswith('/'):  # 正经注释：确保URL以斜杠结尾 / 大白话注释：网址末尾没有斜杠就加上
                base_url += '/'
            return base_url
        except KeyError:  # 正经注释：环境变量不存在时抛出友好错误 / 大白话注释：没找到网址就报错
            raise Exception(
                "SearxNG URL not found. Please set the SEARX_URL environment variable. "
                "You can find public instances at https://searx.space/"
            )

    def search(self, max_results: int = 10) -> List[Dict[str, str]]:
        """
        执行SearxNG搜索查询。

        【正经注释】
        通过SearxNG JSON API执行搜索，指定返回JSON格式结果，
        将结果标准化为{href, body}格式返回。

        【大白话注释】
        真正去SearxNG搜东西。让SearxNG返回JSON格式的结果，
        然后整理成统一格式给你。

        Args:
            max_results: 最大返回结果数，默认10

        Returns:
            包含href和body的搜索结果列表

        Raises:
            Exception: 搜索请求或解析失败时抛出
        """
        search_url = urljoin(self.base_url, "search")  # 正经注释：拼接搜索API的完整URL / 大白话注释：把搜索接口地址拼出来
        # TODO: Add support for query domains  # 正经注释：待办：添加域名过滤支持 / 大白话注释：以后要加的功能
        params = {
            # The search query.
            'q': self.query,  # 正经注释：搜索查询参数 / 大白话注释：搜什么关键词
            # Output format of results. Format needs to be activated in searxng config.
            'format': 'json'  # 正经注释：指定输出格式为JSON（需在SearxNG配置中启用） / 大白话注释：让SearxNG返回JSON格式
        }

        try:
            response = requests.get(  # 正经注释：发送GET请求到SearxNG / 大白话注释：正式向SearxNG发搜索请求
                search_url,
                params=params,
                headers={'Accept': 'application/json'}  # 正经注释：指定接受JSON响应 / 大白话注释：告诉服务器我要JSON
            )
            response.raise_for_status()  # 正经注释：检查HTTP状态码 / 大白话注释：看看请求有没有成功
            results = response.json()  # 正经注释：解析JSON响应 / 大白话注释：把返回数据解析出来

            # Normalize results to match the expected format
            search_response = []  # 正经注释：初始化标准化结果列表 / 大白话注释：准备箱子装结果
            for result in results.get('results', [])[:max_results]:  # 正经注释：遍历结果列表，截取前max_results条 / 大白话注释：一条一条看，最多看要的条数
                search_response.append({
                    "href": result.get('url', ''),  # 正经注释：结果URL / 大白话注释：网页链接
                    "body": result.get('content', '')  # 正经注释：结果内容 / 大白话注释：网页简介
                })

            return search_response  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去

        except requests.exceptions.RequestException as e:  # 正经注释：捕获HTTP请求异常 / 大白话注释：网络出错了就报错
            raise Exception(f"Error querying SearxNG: {str(e)}")
        except json.JSONDecodeError:  # 正经注释：捕获JSON解析异常 / 大白话注释：返回的数据解析不了就报错
            raise Exception("Error parsing SearxNG response")
