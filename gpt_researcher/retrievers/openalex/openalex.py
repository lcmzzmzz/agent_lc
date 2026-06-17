"""
OpenAlex 学术文献搜索引擎检索器。

【正经注释】本模块实现了基于OpenAlex API的学术文献搜索功能。
OpenAlex是一个开放的学术作品目录，无需API密钥即可使用（默认速率限制）。
支持通过邮件和API密钥获取更优的速率限制，提供相关度、引用次数和出版日期三种排序方式。

【大白话注释】这个文件是用来搜OpenAlex的。OpenAlex是个免费的学术论文数据库，
不用密钥就能搜。如果你给它一个邮箱地址，它对你更友好（请求限制更宽松）。
搜完把论文的标题、链接和摘要整理好给你。
"""

import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读系统里存的配置
from typing import Dict, List, Optional  # 正经注释：类型提示相关导入 / 大白话注释：类型标注用的

import requests  # 正经注释：HTTP请求库，用于调用OpenAlex API / 大白话注释：发网络请求用的工具


class OpenAlexSearch:
    """
    OpenAlex 学术文献搜索引擎检索器。

    【正经注释】
    通过OpenAlex REST API实现的学术文献搜索类。OpenAlex (https://openalex.org)
    是一个开放的学术作品目录，默认无需API密钥即可访问。
    可选环境变量：
    - OPENALEX_EMAIL: 加入OpenAlex礼貌池，获得更稳定的速率限制（推荐生产环境使用）
    - OPENALEX_API_KEY: 认证访问，获得更高的速率限制（在 https://openalex.org/ 免费注册）

    【大白话注释】
    这个类就是帮你搜OpenAlex学术论文的。OpenAlex是个免费的学术数据库，
    不需要密钥就能用。如果你有邮箱或API密钥，它可以对你更"客气"（限制更少）。
    """

    BASE_URL = "https://api.openalex.org/works"  # 正经注释：OpenAlex Works API端点 / 大白话注释：OpenAlex论文搜索的网址
    VALID_SORT_CRITERIA = [  # 正经注释：支持的排序标准列表 / 大白话注释：可以用哪几种方式排序
        "relevance_score:desc",  # 正经注释：按相关度降序 / 大白话注释：最相关的排最前
        "cited_by_count:desc",  # 正经注释：按引用次数降序 / 大白话注释：被引用最多的排最前
        "publication_date:desc",  # 正经注释：按出版日期降序 / 大白话注释：最新的排最前
    ]

    def __init__(self, query: str, sort: str = "relevance_score:desc", query_domains=None):
        """
        初始化OpenAlexSearch检索器。

        【正经注释】
        接收搜索查询语句和排序标准，从环境变量获取可选的邮件和API密钥配置。

        【大白话注释】
        准备工作——记下要搜什么关键词、按什么方式排序，
        顺便看看系统里有没有配邮箱和API密钥。

        :param query: 搜索查询关键词
        :param sort: 排序标准，必须是VALID_SORT_CRITERIA中的一种
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        assert sort in self.VALID_SORT_CRITERIA, f"Invalid sort criterion: {sort}"  # 正经注释：断言排序参数合法性 / 大白话注释：排序方式不对就报错
        self.sort = sort  # 正经注释：保存排序标准 / 大白话注释：记住排序方式
        self.email: Optional[str] = os.environ.get("OPENALEX_EMAIL")  # 正经注释：从环境变量获取可选的邮箱地址 / 大白话注释：看看有没有配邮箱
        self.api_key: Optional[str] = os.environ.get("OPENALEX_API_KEY")  # 正经注释：从环境变量获取可选的API密钥 / 大白话注释：看看有没有配API密钥

    def search(self, max_results: int = 20) -> List[Dict[str, str]]:
        """
        执行OpenAlex学术文献搜索。

        【正经注释】
        通过OpenAlex API执行搜索查询，自动从倒排索引中重建摘要文本，
        优先选择开放获取的PDF链接，返回标准化的搜索结果列表。

        【大白话注释】
        真正去OpenAlex搜论文。OpenAlex存摘要的方式比较特别（倒排索引），
        这里会把它还原成正常文字。还会优先找能免费下载PDF的链接。

        :param max_results: 最大返回结果数（单次请求上限25）
        :return: 包含title、href和body的搜索结果列表
        """
        params = {
            "search": self.query,  # 正经注释：搜索查询语句 / 大白话注释：搜什么关键词
            "per_page": min(max_results, 25),  # 正经注释：每页结果数，上限25 / 大白话注释：一次最多要25条
            "sort": self.sort,  # 正经注释：排序标准 / 大白话注释：按什么顺序排
        }
        if self.email:  # 正经注释：如果配置了邮箱则加入礼貌池 / 大白话注释：有邮箱就告诉OpenAlex"我是谁"
            params["mailto"] = self.email
        if self.api_key:  # 正经注释：如果配置了API密钥则附加认证信息 / 大白话注释：有密钥就带上身份证明
            params["api_key"] = self.api_key

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)  # 正经注释：发送GET请求到OpenAlex API / 大白话注释：正式向OpenAlex发搜索请求
            response.raise_for_status()  # 正经注释：检查HTTP状态码 / 大白话注释：看看请求有没有成功
        except requests.RequestException as e:  # 正经注释：请求异常时打印错误并返回空列表 / 大白话注释：出错了就告诉你，返回空结果
            print(f"An error occurred while accessing OpenAlex API: {e}")
            return []

        results = response.json().get("results", [])  # 正经注释：从响应中提取结果列表 / 大白话注释：把搜到的论文拿出来
        search_result = []  # 正经注释：初始化标准化结果列表 / 大白话注释：准备空箱子装结果
        for result in results:  # 正经注释：遍历每个搜索结果 / 大白话注释：一篇一篇地看
            title = result.get("title") or "No Title"  # 正经注释：获取论文标题 / 大白话注释：论文叫什么
            href = self._pick_href(result)  # 正经注释：智能选择最佳链接 / 大白话注释：挑一个最好的链接
            body = self._reconstruct_abstract(result.get("abstract_inverted_index"))  # 正经注释：从倒排索引重建摘要 / 大白话注释：把摘要从特殊格式还原成正常文字

            if href:  # 正经注释：仅有链接的结果才添加到结果列表 / 大白话注释：有链接的才要
                search_result.append(
                    {
                        "title": title,  # 正经注释：论文标题 / 大白话注释：论文名字
                        "href": href,  # 正经注释：论文URL / 大白话注释：论文链接
                        "body": body or "Abstract not available",  # 正经注释：论文摘要，无摘要时显示提示 / 大白话注释：论文简介，没简介就写"暂无简介"
                    }
                )

        return search_result  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去

    @staticmethod
    def _pick_href(result: dict) -> Optional[str]:
        """
        智能选择最佳URL链接。

        【正经注释】
        按优先级选择URL：开放获取PDF > 主要位置的着陆页URL > OpenAlex作品URL。
        确保返回最有价值的链接给用户。

        【大白话注释】
        帮你挑一个最好的链接。优先选能免费下载PDF的链接，
        其次选论文的官方页面，最后用OpenAlex自己的页面链接。

        Args:
            result: 单条搜索结果的原始字典

        Returns:
            最佳URL字符串，若无可用链接则返回None
        """
        oa_location = result.get("best_oa_location") or {}  # 正经注释：获取最佳开放获取位置 / 大白话注释：看看有没有免费PDF
        pdf_url = oa_location.get("pdf_url")  # 正经注释：获取PDF下载URL / 大白话注释：PDF下载地址
        if pdf_url:  # 正经注释：有PDF链接则直接返回 / 大白话注释：有免费PDF就用这个
            return pdf_url

        primary = result.get("primary_location") or {}  # 正经注释：获取主要位置信息 / 大白话注释：看看论文的主页在哪
        landing = primary.get("landing_page_url")  # 正经注释：获取着陆页URL / 大白话注释：论文官方页面地址
        if landing:  # 正经注释：有着陆页URL则返回 / 大白话注释：有官方页面就用这个
            return landing

        return result.get("id")  # 正经注释：返回OpenAlex作品ID作为兜底URL / 大白话注释：都没有就用OpenAlex的链接

    @staticmethod
    def _reconstruct_abstract(inverted: Optional[dict]) -> Optional[str]:
        """
        从OpenAlex倒排索引格式重建摘要文本。

        【正经注释】
        OpenAlex将摘要存储为倒排索引格式（单词 -> 位置列表）。
        此方法将其还原为原始文本字符串。

        【大白话注释】
        OpenAlex存摘要的方式很特别：它不是存一段文字，而是存每个词在第几个位置。
        这个函数就是把这种"密码本"翻译回正常的一段话。

        Args:
            inverted: 倒排索引字典，格式为 {单词: [位置列表]}

        Returns:
            重建的摘要文本字符串，若输入为空则返回None
        """
        if not inverted:  # 正经注释：空输入直接返回None / 大白话注释：没有摘要就返回空
            return None
        positions: List[tuple] = []  # 正经注释：初始化(位置, 单词)元组列表 / 大白话注释：准备一个列表把每个词和它的位置记下来
        for word, indexes in inverted.items():  # 正经注释：遍历倒排索引中的每个单词及其位置 / 大白话注释：一个词一个词地看
            for i in indexes:  # 正经注释：将该单词的每个出现位置记录下来 / 大白话注释：这个词可能出现在多个位置
                positions.append((i, word))
        positions.sort(key=lambda x: x[0])  # 正经注释：按位置升序排序 / 大白话注释：按位置排好队
        return " ".join(word for _, word in positions)  # 正经注释：拼接为完整文本 / 大白话注释：按顺序把词拼成一段话
