"""
【正经注释】基于 FireCrawl API 的网页内容提取模块，通过 FireCrawl 云服务将网页转换为
Markdown 格式的纯净内容，同时使用 BeautifulSoup 辅助提取图片信息。

【大白话注释】这个文件用 FireCrawl 服务来抓网页内容。FireCrawl 是一个专门的网页抓取服务，
它会把网页内容转成干净的 Markdown 格式。图片还得靠 BeautifulSoup 从 HTML 里提取。
需要设置 FIRECRAWL_API_KEY 环境变量才能用。
"""
from bs4 import BeautifulSoup  # 正经注释：HTML 解析库，用于提取图片 / 大白话注释：解析 HTML 的工具，用来找图片
import os  # 正经注释：操作系统接口，用于读取环境变量 / 大白话注释：用来读取环境变量里的 API 密钥
from ..utils import get_relevant_images  # 正经注释：导入图片提取工具函数 / 大白话注释：从工具箱里拿找图片的工具

class FireCrawl:
    """
    【正经注释】FireCrawl 爬虫类，通过 FireCrawl Python SDK 调用远程 API 将网页内容
    转换为 Markdown 格式，同时结合 BeautifulSoup 提取相关图片和标题。

    【大白话注释】用 FireCrawl 服务抓网页的爬虫。它会调 FireCrawl 的 API 把网页转成 Markdown，
    然后用 BeautifulSoup 补充提取图片。需要先配置 API Key。
    """

    def __init__(self, link, session=None):
        self.link = link  # 正经注释：存储待抓取的 URL / 大白话注释：记住要抓的网址
        self.session = session  # 正经注释：存储 HTTP 会话对象 / 大白话注释：HTTP 会话
        from firecrawl import FirecrawlApp  # 正经注释：延迟导入 FireCrawl SDK / 大白话注释：用到才导入 FireCrawl
        self.firecrawl = FirecrawlApp(api_key=self.get_api_key(), api_url=self.get_server_url())  # 正经注释：初始化 FireCrawl 客户端 / 大白话注释：用 API Key 创建 FireCrawl 客户端

    def get_api_key(self) -> str:
        """
        【正经注释】从环境变量 FIRECRAWL_API_KEY 获取 FireCrawl API 密钥。

        Returns:
            str: FireCrawl API 密钥

        Raises:
            Exception: 环境变量未设置时抛出异常

        【大白话注释】从环境变量里读 FireCrawl 的 API Key。没配置就报错告诉你去设置。
        """
        try:
            api_key = os.environ["FIRECRAWL_API_KEY"]  # 正经注释：读取环境变量 / 大白话注释：去环境变量里找 API Key
        except KeyError:
            raise Exception(
                "FireCrawl API key not found. Please set the FIRECRAWL_API_KEY environment variable.")  # 正经注释：未找到则抛出友好错误 / 大白话注释：找不到就报错，让你去设环境变量
        return api_key

    def get_server_url(self) -> str:
        """
        【正经注释】从环境变量 FIRECRAWL_SERVER_URL 获取 FireCrawl 服务器地址，
        未设置时默认使用官方服务器 https://api.firecrawl.dev。

        Returns:
            str: FireCrawl 服务器 URL

        【大白话注释】读 FireCrawl 服务器地址，一般用官方的就行。
        如果你自己部署了 FireCrawl 服务，可以通过环境变量指定你自己的地址。
        """
        try:
            server_url = os.environ["FIRECRAWL_SERVER_URL"]  # 正经注释：读取自定义服务器地址 / 大白话注释：看看有没有配置自己的服务器
        except KeyError:
            server_url = 'https://api.firecrawl.dev'  # 正经注释：默认使用官方服务器 / 大白话注释：没配置就用官方的
        return server_url

    def scrape(self) -> tuple:
        """
        【正经注释】使用 FireCrawl SDK 抓取网页内容并转换为 Markdown 格式，
        同时通过 BeautifulSoup 从原始 HTML 中提取图片信息。
        检查响应的 metadata 中的错误码和状态码，确保抓取成功。

        Returns:
            tuple: (content, image_urls, title) Markdown 内容、图片列表和标题；
                   异常时返回 ("", [], "")

        【大白话注释】开始抓网页！先用 FireCrawl API 把网页内容变成 Markdown，
        再用 BeautifulSoup 从 HTML 里把图片找出来。如果 FireCrawl 报错了就返回空结果。
        """

        try:
            # Fixed: Changed from scrape_url() to scrape() to match FireCrawl SDK v4.6.0+
            # 正经注释：调用 FireCrawl SDK 的 scrape 方法获取 Markdown 格式内容 / 大白话注释：用 FireCrawl 的 API 抓网页，要 Markdown 格式
            response = self.firecrawl.scrape(url=self.link, formats=["markdown"])

            # Check if the page has been scraped successfully
            # Fixed: Access metadata attributes directly (not as dict keys)
            # 正经注释：检查 metadata 中的错误信息 / 大白话注释：看看 FireCrawl 有没有报错
            if response.metadata and response.metadata.error:
                print("Scrape failed! : " + str(response.metadata.error))
                return "", [], ""
            elif response.metadata and response.metadata.status_code and response.metadata.status_code != 200:  # 正经注释：检查 HTTP 状态码 / 大白话注释：看看返回的状态码是不是 200（成功）
                print(f"Scrape failed! Status code: {response.metadata.status_code}")
                return "", [], ""

            # Extract the content (markdown) and title from FireCrawl response
            # Fixed: Access attributes directly (not as dict keys)
            # 正经注释：从 FireCrawl 响应中提取 Markdown 内容和标题 / 大白话注释：把 FireCrawl 返回的内容和标题拿出来
            content = response.markdown if response.markdown else ""
            title = response.metadata.title if response.metadata and response.metadata.title else ""

            # Parse the HTML content of the response to create a BeautifulSoup object for the utility functions
            # 正经注释：通过 HTTP 请求获取原始 HTML，用于 BeautifulSoup 提取图片 / 大白话注释：FireCrawl 只给了文字，图片还得自己去 HTML 里找
            response_bs = self.session.get(self.link, timeout=4)
            soup = BeautifulSoup(
                response_bs.content, "lxml", from_encoding=response_bs.encoding
            )

            # Get relevant images using the utility function
            # 正经注释：使用工具函数提取相关图片 / 大白话注释：找出页面里有用的图片
            image_urls = get_relevant_images(soup, self.link)

            return content, image_urls, title  # 正经注释：返回 Markdown 内容、图片列表和标题 / 大白话注释：把结果打包返回

        except Exception as e:  # 正经注释：捕获所有异常并返回空结果 / 大白话注释：出错了就返回空的
            print("Error! : " + str(e))
            return "", [], ""
