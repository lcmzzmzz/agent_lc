"""
DuckDuckGo 搜索引擎检索器。

【正经注释】本模块实现了基于DuckDuckGo搜索API的网页搜索功能，
通过ddgs（DuckDuckGo Search）第三方库执行无区域偏见的搜索查询，
返回标准化的搜索结果格式。

【大白话注释】这个文件是用来搜DuckDuckGo的。DuckDuckGo是一个注重隐私的搜索引擎，
不用API密钥就能搜。你给它关键词，它就帮你搜网页，搜完整理好给你。
"""

from itertools import islice  # 正经注释：迭代器切片工具（当前未直接使用） / 大白话注释：切分迭代器用的（这里其实没用到）
from ..utils import check_pkg  # 正经注释：从父模块导入包检查工具函数 / 大白话注释：导入检查包装没装好的函数


class Duckduckgo:
    """
    DuckDuckGo 搜索引擎检索器。

    【正经注释】
    通过ddgs（DuckDuckGo Search）第三方Python库实现的网页搜索类。
    使用全球区域(wt-wt)进行无偏见搜索，返回结构化的搜索结果列表。

    【大白话注释】
    这个类就是帮你用DuckDuckGo搜东西的。不需要API密钥，
    用的是ddgs这个第三方库。搜完把结果整理好给你。
    """

    def __init__(self, query, query_domains=None):
        """
        初始化Duckduckgo检索器。

        【正经注释】
        构造函数，检查ddgs包是否安装，初始化DDGS客户端实例，
        并保存搜索查询语句。

        【大白话注释】
        准备工作——先看看ddgs包装了没有，没装就提醒你装。
        然后创建一个DuckDuckGo搜索客户端，记下要搜的关键词。

        Args:
            query: 搜索查询关键词
            query_domains: 域名过滤列表（当前版本未实现）
        """
        check_pkg('ddgs')  # 正经注释：检查ddgs包是否已安装 / 大白话注释：看看ddgs包装了没有
        from ddgs import DDGS  # 正经注释：延迟导入DDGS类 / 大白话注释：把DuckDuckGo的搜索工具拿进来
        self.ddg = DDGS()  # 正经注释：创建DDGS客户端实例 / 大白话注释：创建一个DuckDuckGo搜索客户端
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站（目前还没实现）

    def search(self, max_results=5):
        """
        执行DuckDuckGo搜索。

        【正经注释】
        通过ddgs库执行文本搜索，使用全球区域(wt-wt)确保搜索结果无区域偏见，
        异常时返回空列表而不中断程序。

        【大白话注释】
        真正去DuckDuckGo搜东西。用的是全球区域，不偏向任何国家。
        搜出错了也不崩溃，返回空结果就行。

        :param max_results: 最大返回结果数，默认5
        :return: 搜索结果列表
        """
        # TODO: Add support for query domains  # 正经注释：待办：添加域名过滤支持 / 大白话注释：以后要加的功能——限定搜哪些网站
        try:
            search_response = self.ddg.text(self.query, region='wt-wt', max_results=max_results)  # 正经注释：使用DDGS客户端执行文本搜索，wt-wt表示全球区域 / 大白话注释：正式去DuckDuckGo搜，全球模式不偏向任何地区
        except Exception as e:  # 正经注释：捕获搜索异常并返回空列表 / 大白话注释：出错了就记一下，返回空结果
            print(f"Error: {e}. Failed fetching sources. Resulting in empty response.")
            search_response = []
        return search_response  # 正经注释：返回搜索结果 / 大白话注释：把搜到的结果交出去
