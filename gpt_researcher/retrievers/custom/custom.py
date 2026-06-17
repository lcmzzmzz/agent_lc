"""
自定义API检索器。

【正经注释】本模块实现了通用自定义HTTP API检索器，允许用户通过环境变量
配置自定义的搜索端点和参数，实现与任意HTTP搜索API的集成。

【大白话注释】这个文件是个"万能插头"——如果你用的搜索引擎不在默认列表里，
你可以自己搭一个搜索API，然后通过环境变量告诉它地址和参数就行。
"""

from typing import Any, Dict, List, Optional  # 正经注释：类型提示相关导入 / 大白话注释：类型标注用的
import requests  # 正经注释：HTTP请求库 / 大白话注释：发网络请求用的
import os  # 正经注释：操作系统接口模块 / 大白话注释：读环境变量用的


class CustomRetriever:
    """
    自定义API检索器。

    【正经注释】
    通用的HTTP API检索器实现，通过RETRIEVER_ENDPOINT环境变量指定搜索端点URL，
    通过RETRIEVER_ARG_前缀的环境变量传递额外参数，实现与任意搜索API的灵活集成。

    【大白话注释】
    这个类让你可以用自己的搜索API。你只要把API地址设在环境变量里，
    再把需要的参数也设好，它就会帮你去调这个API拿结果。

    需要设置的环境变量：
    - RETRIEVER_ENDPOINT: 你的搜索API地址（必须）
    - RETRIEVER_ARG_xxx: 额外参数（可选）
    """

    def __init__(self, query: str, query_domains=None):
        """
        初始化自定义检索器。

        【正经注释】
        从环境变量读取API端点URL，收集所有RETRIEVER_ARG_前缀的参数，
        并保存搜索查询语句。

        【大白话注释】
        准备工作——去环境变量里找你配好的API地址和参数，
        找不到API地址就报错。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表
        """
        self.endpoint = os.getenv('RETRIEVER_ENDPOINT')  # 正经注释：从环境变量获取自定义API端点URL / 大白话注释：去读你设的API地址
        if not self.endpoint:  # 正经注释：验证端点URL是否存在 / 大白话注释：没设地址就报错
            raise ValueError("RETRIEVER_ENDPOINT environment variable not set")

        self.params = self._populate_params()  # 正经注释：收集所有自定义参数 / 大白话注释：把额外的参数也收集起来
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥

    def _populate_params(self) -> Dict[str, Any]:
        """
        从环境变量中收集RETRIEVER_ARG_前缀的参数。

        【正经注释】
        扫描所有以RETRIEVER_ARG_为前缀的环境变量，去除前缀并转小写后
        作为API请求参数返回。

        【大白话注释】
        把环境变量里所有以RETRIEVER_ARG_开头的变量都找出来，
        去掉前缀后变成小写的参数名，比如RETRIEVER_ARG_FOO变成foo。

        Returns:
            Dict[str, Any]: 参数字典
        """
        return {
            key[len('RETRIEVER_ARG_'):].lower(): value
            for key, value in os.environ.items()
            if key.startswith('RETRIEVER_ARG_')
        }

    def search(self, max_results: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        通过自定义API端点执行搜索。

        【正经注释】
        向自定义端点发送GET请求，附带所有配置参数和查询语句，
        返回API的原始JSON响应。

        【大白话注释】
        真正去调你的自定义API搜东西。把参数和关键词一起发过去，
        把返回的结果直接交给你。

        :param max_results: 最大返回结果数（当前未使用）
        :return: JSON格式的搜索结果列表，失败时返回None
        """
        try:
            response = requests.get(self.endpoint, params={**self.params, 'query': self.query})  # 正经注释：发送GET请求到自定义端点 / 大白话注释：带着参数和关键词去调API
            response.raise_for_status()  # 正经注释：检查HTTP响应状态码 / 大白话注释：看看请求有没有成功
            return response.json()  # 正经注释：返回解析后的JSON响应 / 大白话注释：把API返回的数据解析出来交出去
        except requests.RequestException as e:  # 正经注释：捕获请求异常并打印错误 / 大白话注释：请求出错了就告诉你，返回None
            print(f"Failed to retrieve search results: {e}")
            return None
