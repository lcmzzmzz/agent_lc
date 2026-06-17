"""
Exa AI 搜索引擎检索器。

【正经注释】本模块实现了基于Exa API的智能网页搜索功能，
支持神经搜索(neural)和关键词搜索(keyword)两种模式，
以及查找相似文档和获取文档内容等高级功能。

【大白话注释】这个文件是用来搜Exa的。Exa是一个AI驱动的搜索引擎，
搜得比较智能。它不仅能搜网页，还能帮你找"跟这个网页类似的其他网页"，
或者直接拿到某个网页的完整内容。
"""

import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读系统里存的API密钥
from ..utils import check_pkg  # 正经注释：从父模块导入包检查工具函数 / 大白话注释：导入检查包装没装好的函数


class ExaSearch:
    """
    Exa AI 搜索引擎检索器。

    【正经注释】
    通过Exa官方Python SDK实现的智能网页搜索类。
    支持神经搜索和关键词搜索两种模式，提供search（搜索）、
    find_similar（查找相似文档）和get_contents（获取文档内容）三种核心操作。

    【大白话注释】
    这个类就是帮你用Exa搜东西的。Exa是个AI搜索引擎，搜得比传统搜索引擎聪明。
    它能搜网页、找相似网页、拿网页内容，功能挺全的。
    """

    def __init__(self, query, query_domains=None):
        """
        初始化ExaSearch对象。

        【正经注释】
        检查exa_py包是否安装，从环境变量获取API密钥，
        初始化Exa客户端实例。

        【大白话注释】
        准备工作——先看看exa_py包装了没有，然后去拿Exa的API密钥，
        最后创建一个Exa客户端准备搜索。

        Args:
            query: 搜索查询关键词
            query_domains: 要限定搜索的域名列表
        """
        # This validation is necessary since exa_py is optional
        check_pkg("exa_py")  # 正经注释：检查exa_py包是否已安装，因为它是可选依赖 / 大白话注释：看看exa_py装了没，这个包不是默认装的
        from exa_py import Exa  # 正经注释：导入Exa SDK客户端类 / 大白话注释：把Exa的工具包拿进来
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.api_key = self._retrieve_api_key()  # 正经注释：获取API密钥 / 大白话注释：去拿Exa的钥匙
        self.client = Exa(api_key=self.api_key)  # 正经注释：使用API密钥创建Exa客户端实例 / 大白话注释：用钥匙创建一个Exa客户端
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站

    def _retrieve_api_key(self):
        """
        从环境变量获取Exa API密钥。

        【正经注释】
        从系统环境变量中读取EXA_API_KEY，若未设置则抛出异常
        并提供获取密钥的URL指引。

        【大白话注释】
        去系统里找Exa的API钥匙。找不到就告诉你去Exa官网申请。

        Returns:
            str: Exa API密钥

        Raises:
            Exception: API密钥未设置时抛出
        """
        try:
            api_key = os.environ["EXA_API_KEY"]  # 正经注释：从环境变量读取Exa API密钥 / 大白话注释：去系统里找Exa的钥匙
        except KeyError:  # 正经注释：密钥不存在时抛出友好错误 / 大白话注释：没找到钥匙就报错
            raise Exception(
                "Exa API key not found. Please set the EXA_API_KEY environment variable. "
                "You can obtain your key from https://exa.ai/"
            )
        return api_key  # 正经注释：返回API密钥 / 大白话注释：把钥匙交出去

    def search(
        self, max_results=10, use_autoprompt=False, search_type="neural", **filters
    ):
        """
        使用Exa API执行搜索。

        【正经注释】
        支持神经搜索(neural)和关键词搜索(keyword)两种模式，
        可选启用自动提示词优化，支持域名过滤等高级筛选条件。

        【大白话注释】
        正式去Exa搜东西。默认用"神经搜索"模式（AI理解的搜索），
        你也可以换成"关键词搜索"模式。还能限定只搜某些网站的。

        Args:
            max_results: 最大返回结果数，默认10
            use_autoprompt: 是否使用自动提示词优化，默认False
            search_type: 搜索类型，"neural"或"keyword"，默认"neural"
            **filters: 额外过滤条件（如日期范围、域名等）

        Returns:
            list: 包含href和body的搜索结果列表
        """
        results = self.client.search(  # 正经注释：调用Exa客户端的搜索方法 / 大白话注释：正式向Exa发搜索请求
            self.query,
            type=search_type,  # 正经注释：指定搜索类型 / 大白话注释：用什么模式搜
            use_autoprompt=use_autoprompt,  # 正经注释：是否启用自动提示词 / 大白话注释：让Exa自动优化搜索词
            num_results=max_results,  # 正经注释：结果数量限制 / 大白话注释：要几条结果
            include_domains=self.query_domains,  # 正经注释：限定搜索域名 / 大白话注释：只搜这些网站
            **filters  # 正经注释：传入额外过滤条件 / 大白话注释：其他过滤条件
        )

        search_response = [
            {"href": result.url, "body": result.text} for result in results.results  # 正经注释：将Exa结果转换为标准{href, body}格式 / 大白话注释：把Exa返回的结果整理成统一格式
        ]
        return search_response  # 正经注释：返回搜索结果列表 / 大白话注释：把结果交出去

    def find_similar(self, url, exclude_source_domain=False, **filters):
        """
        查找与指定URL相似的文档。

        【正经注释】
        使用Exa的find_similar功能，基于给定URL查找语义相似的网页文档，
        可选择排除源站域名下的结果。

        【大白话注释】
        给它一个网页链接，它帮你找"跟这个网页内容类似"的其他网页。
        还可以选择不要同一网站的结果。

        Args:
            url: 目标URL，用于查找相似文档
            exclude_source_domain: 是否排除源站域名，默认False
            **filters: 额外过滤条件

        Returns:
            list: 相似文档列表
        """
        results = self.client.find_similar(  # 正经注释：调用Exa客户端的相似文档查找方法 / 大白话注释：让Exa找相似的网页
            url, exclude_source_domain=exclude_source_domain, **filters
        )

        similar_response = [
            {"href": result.url, "body": result.text} for result in results.results  # 正经注释：转换为标准格式 / 大白话注释：整理成统一格式
        ]
        return similar_response  # 正经注释：返回相似文档列表 / 大白话注释：把找到的相似网页交出去

    def get_contents(self, ids, **options):
        """
        获取指定ID的文档内容。

        【正经注释】
        使用Exa的get_contents功能，根据文档ID获取完整的文档文本内容，
        支持额外的内容获取选项。

        【大白话注释】
        给它一些文档ID，它帮你把这些文档的完整内容拿回来。

        Args:
            ids: 文档ID列表
            **options: 额外的内容获取选项

        Returns:
            list: 文档内容列表，包含id和content字段
        """
        results = self.client.get_contents(ids, **options)  # 正经注释：调用Exa客户端获取文档内容 / 大白话注释：让Exa把文档内容拿回来

        contents_response = [
            {"id": result.id, "content": result.text} for result in results.results  # 正经注释：转换为{id, content}格式 / 大白话注释：整理成统一格式
        ]
        return contents_response  # 正经注释：返回文档内容列表 / 大白话注释：把文档内容交出去
