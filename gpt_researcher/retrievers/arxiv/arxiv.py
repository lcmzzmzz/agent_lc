"""
Arxiv 学术论文搜索引擎检索器。

【正经注释】本模块实现了基于Arxiv API的学术论文检索功能，
支持按相关度或提交日期排序，返回论文标题、PDF链接及摘要信息。

【大白话注释】这个文件是用来搜Arxiv论文的。你给它一个关键词，它就跑去Arxiv网站
帮你找论文，然后把论文标题、下载链接和摘要都整理好给你。
"""

import arxiv  # 正经注释：Arxiv官方Python SDK，用于访问Arxiv论文数据库 / 大白话注释：连Arxiv论文库用的工具包


class ArxivSearch:
    """
    Arxiv API 论文检索器。

    【正经注释】
    通过Arxiv官方Python SDK实现的学术论文搜索类。支持按相关度(Relevance)
    或提交日期(SubmittedDate)排序，返回结构化的论文搜索结果列表。

    【大白话注释】
    这个类就是帮你搜Arxiv论文的。你告诉它搜什么、按什么排序，
    它就去Arxiv网站帮你找论文，找完把结果整理成列表还给你。
    """

    def __init__(self, query, sort='Relevance', query_domains=None):
        """
        初始化Arxiv检索器。

        【正经注释】
        构造函数，接收搜索查询语句和排序条件，初始化Arxiv客户端
        并设置排序策略。

        【大白话注释】
        就是准备工作——记下你要搜什么关键词、按什么顺序排列结果。

        Args:
            query: 搜索查询关键词
            sort: 排序方式，'Relevance'(相关度) 或 'SubmittedDate'(提交日期)
            query_domains: 域名过滤列表（Arxiv不支持此参数，保留接口一致性）
        """
        self.arxiv = arxiv  # 正经注释：保存arxiv模块引用 / 大白话注释：把arxiv工具包存起来后面用
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住用户要搜什么
        assert sort in ['Relevance', 'SubmittedDate'], "Invalid sort criterion"  # 正经注释：断言排序参数合法性 / 大白话注释：检查排序方式对不对，不对就报错
        self.sort = arxiv.SortCriterion.SubmittedDate if sort == 'SubmittedDate' else arxiv.SortCriterion.Relevance  # 正经注释：将排序字符串映射为arxiv SDK的枚举值 / 大白话注释：把文字版的排序方式翻译成程序认识的形式


    def search(self, max_results=5):
        """
        执行Arxiv论文搜索。

        【正经注释】
        调用Arxiv API执行搜索查询，获取论文结果列表，并将其转换为
        标准化的{title, href, body}字典格式返回。

        【大白话注释】
        真正去Arxiv搜论文。搜完之后把每篇论文的标题、下载链接和摘要
        都整理好，装在一个列表里还给你。

        :param max_results: 最大返回结果数，默认5
        :return: 论文搜索结果列表
        """

        arxiv_gen = list(arxiv.Client().results(  # 正经注释：通过Arxiv客户端执行搜索并获取结果迭代器 / 大白话注释：连上Arxiv网站去搜论文，把结果全部拿过来
        self.arxiv.Search(
            query= self.query, #+  # 正经注释：传入搜索查询语句 / 大白话注释：告诉Arxiv搜什么
            max_results=max_results,  # 正经注释：限制最大返回数量 / 大白话注释：最多要几篇论文
            sort_by=self.sort,  # 正经注释：指定排序方式 / 大白话注释：按什么顺序排
        )))

        search_result = []  # 正经注释：初始化结果列表 / 大白话注释：准备一个空箱子装结果

        for result in arxiv_gen:  # 正经注释：遍历Arxiv返回的每个论文结果 / 大白话注释：一篇一篇地看搜到的论文

            search_result.append({  # 正经注释：将论文信息转换为标准格式并添加到结果列表 / 大白话注释：把论文信息整理好放进箱子里
                "title": result.title,  # 正经注释：论文标题 / 大白话注释：论文叫什么名
                "href": result.pdf_url,  # 正经注释：论文PDF下载链接 / 大白话注释：PDF下载地址
                "body": result.summary,  # 正经注释：论文摘要内容 / 大白话注释：论文写了啥的简短介绍
            })

        return search_result  # 正经注释：返回标准化搜索结果列表 / 大白话注释：把装满结果的箱子交给调用者
