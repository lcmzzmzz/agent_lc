"""
Semantic Scholar 学术搜索引擎检索器。

【正经注释】本模块实现了基于Semantic Scholar API的学术论文搜索功能。
Semantic Scholar是AI2（Allen Institute for AI）开发的免费学术搜索引擎，
支持按相关度、引用次数和出版日期排序，仅返回开放获取（Open Access）的论文。

【大白话注释】这个文件是用来搜Semantic Scholar的，这是一个免费的AI学术论文搜索引擎。
搜完之后只给你能免费下载的论文（开放获取的），收费的不给。
"""

from typing import Dict, List  # 正经注释：类型提示相关导入 / 大白话注释：类型标注用的

import requests  # 正经注释：HTTP请求库 / 大白话注释：发网络请求用的工具


class SemanticScholarSearch:
    """
    Semantic Scholar 学术搜索引擎检索器。

    【正经注释】
    通过Semantic Scholar Graph API实现的学术论文搜索类。
    支持三种排序方式：相关度(relevance)、引用次数(citationCount)、出版日期(publicationDate)。
    仅返回开放获取（Open Access）且提供PDF下载的论文。

    【大白话注释】
    这个类就是帮你搜Semantic Scholar论文的。可以按相关度、引用次数或日期排序。
    只给你能免费下载PDF的论文，收费论文直接跳过。

    无需API密钥即可使用（有速率限制）。
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"  # 正经注释：Semantic Scholar论文搜索API端点 / 大白话注释：Semantic Scholar的搜索网址
    VALID_SORT_CRITERIA = ["relevance", "citationCount", "publicationDate"]  # 正经注释：支持的排序标准列表 / 大白话注释：可以用哪几种方式排序

    def __init__(self, query: str, sort: str = "relevance", query_domains=None):
        """
        初始化SemanticScholarSearch检索器。

        【正经注释】
        接收搜索查询语句和排序标准，验证排序参数的合法性。

        【大白话注释】
        准备工作——记下要搜什么关键词、按什么方式排序。

        :param query: 搜索查询关键词
        :param sort: 排序方式，'relevance'(相关度)、'citationCount'(引用次数)或'publicationDate'(出版日期)
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        assert sort in self.VALID_SORT_CRITERIA, "Invalid sort criterion"  # 正经注释：断言排序参数合法性 / 大白话注释：排序方式不对就报错
        self.sort = sort.lower()  # 正经注释：保存小写的排序标准 / 大白话注释：把排序方式转小写存起来

    def search(self, max_results: int = 20) -> List[Dict[str, str]]:
        """
        执行Semantic Scholar搜索。

        【正经注释】
        通过Semantic Scholar API执行搜索查询，请求包含标题、摘要、URL、
        出版信息、作者、开放获取状态和PDF链接等字段。
        仅返回开放获取且可下载PDF的论文。

        【大白话注释】
        真正去Semantic Scholar搜论文。会告诉你论文标题、摘要、能不能免费下载等。
        只返回那些能免费下载PDF的论文。

        :param max_results: 最大返回结果数
        :return: 包含title、href和body的搜索结果列表
        """
        params = {
            "query": self.query,  # 正经注释：搜索查询语句 / 大白话注释：搜什么关键词
            "limit": max_results,  # 正经注释：结果数量限制 / 大白话注释：最多要几条
            "fields": "title,abstract,url,venue,year,authors,isOpenAccess,openAccessPdf",  # 正经注释：请求返回的字段列表 / 大白话注释：要论文的哪些信息
            "sort": self.sort,  # 正经注释：排序标准 / 大白话注释：按什么顺序排
        }

        try:
            response = requests.get(self.BASE_URL, params=params)  # 正经注释：发送GET请求到Semantic Scholar API / 大白话注释：正式发搜索请求
            response.raise_for_status()  # 正经注释：检查HTTP状态码 / 大白话注释：看看请求有没有成功
        except requests.RequestException as e:  # 正经注释：请求异常时打印错误并返回空列表 / 大白话注释：出错了就告诉你，返回空结果
            print(f"An error occurred while accessing Semantic Scholar API: {e}")
            return []

        results = response.json().get("data", [])  # 正经注释：从响应中提取论文数据列表 / 大白话注释：把搜到的论文拿出来
        search_result = []  # 正经注释：初始化标准化结果列表 / 大白话注释：准备箱子装结果

        for result in results:  # 正经注释：遍历每个搜索结果 / 大白话注释：一篇一篇看
            if result.get("isOpenAccess") and result.get("openAccessPdf"):  # 正经注释：仅保留开放获取且有PDF链接的论文 / 大白话注释：只留能免费下载PDF的论文
                search_result.append(
                    {
                        "title": result.get("title", "No Title"),  # 正经注释：论文标题 / 大白话注释：论文名字
                        "href": result["openAccessPdf"].get("url", "No URL"),  # 正经注释：开放获取PDF的URL / 大白话注释：免费PDF下载地址
                        "body": result.get("abstract", "Abstract not available"),  # 正经注释：论文摘要 / 大白话注释：论文简介
                    }
                )

        return search_result  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去
