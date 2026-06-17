"""
【正经注释】基于 Tavily Extract API 的网页内容提取模块，通过 Tavily 云服务从 URL 中
提取纯净的正文内容（raw_content），同时使用 BeautifulSoup 辅助提取图片和标题信息。

【大白话注释】这个文件用 Tavily 的 Extract API 来抓网页内容。Tavily 是一个专门的
网页内容提取服务，你给它一个网址，它就把正文内容还给你。
图片和标题还得靠 BeautifulSoup 从 HTML 里提取。
需要设置 TAVILY_API_KEY 环境变量才能用。
"""
from bs4 import BeautifulSoup  # 正经注释：HTML 解析库，用于提取图片和标题 / 大白话注释：解析 HTML 的工具，用来找图片和标题
import os  # 正经注释：操作系统接口，用于读取环境变量 / 大白话注释：用来读环境变量里的 API 密钥
from ..utils import get_relevant_images, extract_title  # 正经注释：导入图片和标题提取工具函数 / 大白话注释：从工具箱里拿找图片和提取标题的工具

class TavilyExtract:
    """
    【正经注释】Tavily Extract 爬虫类，通过 Tavily Python SDK 调用远程 Extract API
    获取网页的原始正文内容，同时结合 BeautifulSoup 提取相关图片和标题。

    【大白话注释】用 Tavily 服务抓网页的爬虫。先调 Tavily API 拿到正文内容，
    再用 BeautifulSoup 补充提取图片和标题。需要先配置 TAVILY_API_KEY。
    """

    def __init__(self, link, session=None):
        self.link = link  # 正经注释：存储待抓取的 URL / 大白话注释：记住要抓的网址
        self.session = session  # 正经注释：存储 HTTP 会话对象 / 大白话注释：HTTP 会话
        from tavily import TavilyClient  # 正经注释：延迟导入 Tavily SDK / 大白话注释：用到才导入 Tavily
        self.tavily_client = TavilyClient(api_key=self.get_api_key())  # 正经注释：初始化 Tavily 客户端 / 大白话注释：用 API Key 创建 Tavily 客户端

    def get_api_key(self) -> str:
        """
        【正经注释】从环境变量 TAVILY_API_KEY 获取 Tavily API 密钥。

        Returns:
            str: Tavily API 密钥

        Raises:
            Exception: 环境变量未设置时抛出异常

        【大白话注释】从环境变量里读 Tavily 的 API Key。没配置就报错告诉你去设置。
        """
        try:
            api_key = os.environ["TAVILY_API_KEY"]  # 正经注释：读取环境变量 / 大白话注释：去环境变量里找 API Key
        except KeyError:
            raise Exception(
                "Tavily API key not found. Please set the TAVILY_API_KEY environment variable.")  # 正经注释：未找到则抛出友好错误 / 大白话注释：找不到就报错，让你去设环境变量
        return api_key

    def scrape(self) -> tuple:
        """
        【正经注释】使用 Tavily Extract API 提取网页的原始正文内容，
        同时通过 HTTP 请求获取原始 HTML 以使用 BeautifulSoup 提取图片和标题。
        如果 Tavily 返回失败结果则返回空值。

        Returns:
            tuple: (content, image_urls, title) 正文内容、图片列表和标题；
                   异常时返回 ("", [], "")

        【大白话注释】开始抓网页！先用 Tavily API 拿到正文内容，再用 BeautifulSoup
        从 HTML 里把图片和标题找出来。如果 Tavily 说抓取失败了就直接返回空结果。
        """

        try:
            response = self.tavily_client.extract(urls=self.link)  # 正经注释：调用 Tavily Extract API 提取内容 / 大白话注释：让 Tavily 帮我们抓网页内容
            if response['failed_results']:  # 正经注释：检查是否有失败的结果 / 大白话注释：Tavily 说抓失败了？那就算了
                return "", [], ""

            # Parse the HTML content of the response to create a BeautifulSoup object for the utility functions
            # 正经注释：通过 HTTP 请求获取原始 HTML，用于提取图片和标题 / 大白话注释：Tavily 只给了文字，图片和标题还得自己去 HTML 里找
            response_bs = self.session.get(self.link, timeout=4)
            soup = BeautifulSoup(
                response_bs.content, "lxml", from_encoding=response_bs.encoding
            )

            # Since only a single link is provided to tavily_client, the results will contain only one entry.
            # 正经注释：因为只传了一个 URL，结果列表中只有一个条目 / 大白话注释：只查了一个网址，所以结果就一个
            content = response['results'][0]['raw_content']  # 正经注释：提取第一条结果的原始内容 / 大白话注释：把 Tavily 返回的正文拿出来

            # Get relevant images using the utility function
            # 正经注释：使用工具函数提取相关图片 / 大白话注释：找出页面里有用的图片
            image_urls = get_relevant_images(soup, self.link)

            # Extract the title using the utility function
            # 正经注释：使用工具函数提取页面标题 / 大白话注释：拿到页面标题
            title = extract_title(soup)

            return content, image_urls, title  # 正经注释：返回正文、图片列表和标题 / 大白话注释：把结果打包返回

        except Exception as e:  # 正经注释：捕获所有异常并返回空结果 / 大白话注释：出错了就返回空的
            print("Error! : " + str(e))
            return "", [], ""
