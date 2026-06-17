"""
Serper（Google Serper）搜索引擎检索器。

【正经注释】本模块实现了基于Google Serper API的网络搜索功能，
支持国家/地区、语言和时间范围过滤，支持排除指定网站，
支持通过site:语法限定搜索域名范围。

【大白话注释】这个文件是用来搜Serper的。Serper是一个Google搜索API服务，
能帮你搜Google的结果。它比较厉害，可以按国家、语言、时间范围来过滤搜索结果，
还能排除你不想看到的网站。
"""

# Google Serper Retriever

# libraries
import os  # 正经注释：操作系统接口模块，用于读取环境变量 / 大白话注释：用来读系统里存的API密钥和配置
import requests  # 正经注释：HTTP请求库 / 大白话注释：发网络请求用的工具
import json  # 正经注释：JSON解析库 / 大白话注释：解析JSON数据用的


class SerperSearch():
    """
    Serper（Google Serper）搜索引擎检索器。

    【正经注释】
    通过Google Serper Dev API实现的网页搜索类。
    支持国家(gl)、语言(hl)、时间范围(tbs)过滤，
    支持排除指定网站(-site:)和限定域名(site:)。

    【大白话注释】
    这个类就是帮你用Serper搜Google的。功能比较丰富：
    可以按国家搜（比如只搜韩国的结果）、按语言搜、按时间搜，
    还可以排除不想要的网站、只搜特定网站。

    需要设置的环境变量：
    - SERPER_API_KEY: Serper的API密钥
    可选环境变量：
    - SERPER_REGION: 国家代码（如'us', 'kr', 'jp'）
    - SERPER_LANGUAGE: 语言代码（如'en', 'ko', 'ja'）
    - SERPER_TIME_RANGE: 时间范围（如'qdr:h'小时, 'qdr:d'天, 'qdr:w'周, 'qdr:m'月, 'qdr:y'年）
    - SERPER_EXCLUDE_SITES: 要排除的网站列表（逗号分隔）
    """

    def __init__(self, query, query_domains=None, country=None, language=None, time_range=None, exclude_sites=None):
        """
        初始化SerperSearch对象。

        【正经注释】
        接收搜索查询语句和可选的过滤参数，优先使用构造参数，
        其次从环境变量获取默认值。

        【大白话注释】
        准备工作——记下要搜什么、按什么国家/语言/时间来搜、排除哪些网站。
        这些参数可以直接传，也可以通过环境变量设。

        Args:
            query (str): 搜索查询关键词
            query_domains (list, optional): 要限定搜索的域名列表
            country (str, optional): 国家代码（如'us', 'kr', 'jp'）
            language (str, optional): 语言代码（如'en', 'ko', 'ja'）
            time_range (str, optional): 时间范围过滤（如'qdr:h', 'qdr:d', 'qdr:w', 'qdr:m', 'qdr:y'）
            exclude_sites (list, optional): 要排除的网站列表
        """
        self.query = query  # 正经注释：保存搜索查询语句 / 大白话注释：记住要搜啥
        self.query_domains = query_domains or None  # 正经注释：保存域名过滤列表 / 大白话注释：记住要限定搜哪些网站
        self.country = country or os.getenv("SERPER_REGION")  # 正经注释：优先使用参数，否则从环境变量获取国家代码 / 大白话注释：国家从参数拿，没有就从系统拿
        self.language = language or os.getenv("SERPER_LANGUAGE")  # 正经注释：优先使用参数，否则从环境变量获取语言代码 / 大白话注释：语言从参数拿，没有就从系统拿
        self.time_range = time_range or os.getenv("SERPER_TIME_RANGE")  # 正经注释：优先使用参数，否则从环境变量获取时间范围 / 大白话注释：时间范围从参数拿，没有就从系统拿
        self.exclude_sites = exclude_sites or self._get_exclude_sites_from_env()  # 正经注释：优先使用参数，否则从环境变量获取排除网站列表 / 大白话注释：排除哪些网站从参数拿，没有就从系统拿
        self.api_key = self.get_api_key()  # 正经注释：获取API密钥 / 大白话注释：去拿钥匙

    def _get_exclude_sites_from_env(self):
        """
        从环境变量获取要排除的网站列表。

        【正经注释】
        从SERPER_EXCLUDE_SITES环境变量中读取逗号分隔的网站列表，
        去除空白后返回列表。

        【大白话注释】
        去系统里看看有没有配"不要搜哪些网站"。网站之间用逗号分开。

        Returns:
            list: 要排除的网站列表
        """
        exclude_sites_env = os.getenv("SERPER_EXCLUDE_SITES", "")  # 正经注释：从环境变量读取排除网站配置 / 大白话注释：去系统里找排除列表
        if exclude_sites_env:  # 正经注释：配置非空时解析为列表 / 大白话注释：有配置就解析
            # Split by comma and strip whitespace
            return [site.strip() for site in exclude_sites_env.split(",") if site.strip()]  # 正经注释：按逗号分割并去除空白 / 大白话注释：用逗号切开，去掉多余的空格
        return []

    def get_api_key(self):
        """
        从环境变量获取Serper API密钥。

        【正经注释】
        从系统环境变量中读取SERPER_API_KEY，
        若未设置则抛出异常并提供获取指引。

        【大白话注释】
        去系统里找Serper的钥匙。找不到就告诉你去哪申请。

        Returns:
            str: Serper API密钥

        """
        try:
            api_key = os.environ["SERPER_API_KEY"]  # 正经注释：从环境变量读取API密钥 / 大白话注释：去系统里找钥匙
        except Exception:  # 正经注释：密钥不存在时抛出友好错误 / 大白话注释：没找到钥匙就报错
            raise Exception("Serper API key not found. Please set the SERPER_API_KEY environment variable. "
                            "You can get a key at https://serper.dev/")
        return api_key  # 正经注释：返回API密钥 / 大白话注释：把钥匙交出去

    def search(self, max_results=7):
        """
        执行Serper搜索查询，支持国家/语言/时间过滤。

        【正经注释】
        通过Google Serper API执行搜索，支持排除网站(-site:)和
        限定域名(site:)过滤，支持国家(gl)、语言(hl)和时间范围(tbs)参数。
        返回标准化的搜索结果列表。

        【大白话注释】
        真正去Serper搜Google的结果。会用上你设的所有过滤条件：
        排除哪些网站、只搜哪些网站、哪个国家、什么语言、什么时间范围。

        Returns:
            list: 标准化的搜索结果列表，包含title、href和body
        """
        print("Searching with query {0}...".format(self.query))  # 正经注释：输出搜索日志 / 大白话注释：打印正在搜什么
        """Useful for general internet search queries using the Serper API."""

        # Search the query (see https://serper.dev/playground for the format)
        url = "https://google.serper.dev/search"  # 正经注释：Serper API搜索端点 / 大白话注释：Serper的搜索网址

        headers = {
            'X-API-KEY': self.api_key,  # 正经注释：API密钥认证头 / 大白话注释：带上钥匙
            'Content-Type': 'application/json'  # 正经注释：JSON内容类型 / 大白话注释：告诉服务器发JSON
        }

        # Build search parameters
        query_with_filters = self.query  # 正经注释：初始化带过滤条件的查询语句 / 大白话注释：先拿原始关键词

        # Exclude sites using Google search syntax
        if self.exclude_sites:  # 正经注释：添加排除网站的-site:语法 / 大白话注释：把不要的网站排除掉
            for site in self.exclude_sites:
                query_with_filters += f" -site:{site}"

        # Add domain filtering if specified
        if self.query_domains:  # 正经注释：添加域名限定的site:语法 / 大白话注释：限定只搜某些网站
            # Add site:domain1 OR site:domain2 OR ... to the search query
            domain_query = " site:" + " OR site:".join(self.query_domains)  # 正经注释：用OR连接多个site:限定符 / 大白话注释：用"或者"把多个网站连起来
            query_with_filters += domain_query

        search_params = {
            "q": query_with_filters,  # 正经注释：搜索查询参数（含过滤条件） / 大白话注释：搜什么（可能带着各种过滤条件）
            "num": max_results  # 正经注释：结果数量 / 大白话注释：要几条
        }

        # Add optional parameters if they exist
        if self.country:
            search_params["gl"] = self.country  # Geographic location (country)  # 正经注释：设置地理位置（国家） / 大白话注释：限定哪个国家的结果

        if self.language:
            search_params["hl"] = self.language  # Host language  # 正经注释：设置界面语言 / 大白话注释：用什么语言

        if self.time_range:
            search_params["tbs"] = self.time_range  # Time-based search  # 正经注释：设置时间范围过滤 / 大白话注释：限定什么时间段的

        data = json.dumps(search_params)  # 正经注释：将搜索参数序列化为JSON / 大白话注释：把参数变成JSON字符串

        resp = requests.request("POST", url, timeout=10, headers=headers, data=data)  # 正经注释：发送POST请求到Serper API / 大白话注释：正式发搜索请求

        # Preprocess the results
        if resp is None:  # 正经注释：响应为空时返回 / 大白话注释：没回应就返回
            return
        try:
            search_results = json.loads(resp.text)  # 正经注释：解析JSON响应 / 大白话注释：把返回数据解析出来
        except Exception:  # 正经注释：JSON解析失败时返回 / 大白话注释：解析出错就返回
            return
        if search_results is None:  # 正经注释：结果为空时返回 / 大白话注释：没结果就返回
            return

        results = search_results.get("organic", [])  # 正经注释：提取自然搜索结果 / 大白话注释：把搜索结果拿出来
        search_results = []  # 正经注释：重新初始化结果列表 / 大白话注释：准备空箱子

        # Normalize the results to match the format of the other search APIs
        # Excluded sites should already be filtered out by the query parameters
        for result in results:  # 正经注释：遍历并标准化搜索结果 / 大白话注释：一条一条整理
            search_result = {
                "title": result["title"],  # 正经注释：结果标题 / 大白话注释：叫什么
                "href": result["link"],  # 正经注释：结果URL / 大白话注释：链接
                "body": result["snippet"],  # 正经注释：结果摘要 / 大白话注释：简介
            }
            search_results.append(search_result)  # 正经注释：添加到结果列表 / 大白话注释：放进箱子里

        return search_results  # 正经注释：返回搜索结果 / 大白话注释：把结果交出去
