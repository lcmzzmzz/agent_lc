"""
【正经注释】基于 LangChain WebBaseLoader 的网页内容加载模块，使用 LangChain 的
WebBaseLoader 文档加载器获取网页文本内容，同时通过 BeautifulSoup 提取图片和标题信息，
适用于简单的静态网页内容提取场景。

【大白话注释】这个文件用 LangChain 的 WebBaseLoader 来抓网页。WebBaseLoader 是 LangChain
提供的一个简单网页加载器，把网页内容当作文档来处理。图片和标题还是靠 BeautifulSoup 来提取。
适合不需要 JavaScript 渲染的普通网页。
"""
from bs4 import BeautifulSoup  # 正经注释：HTML 解析库，用于提取图片和标题 / 大白话注释：解析 HTML 的工具
from urllib.parse import urljoin  # 正经注释：URL 拼接工具 / 大白话注释：拼网址用的
import requests  # 正经注释：HTTP 请求库 / 大白话注释：发网络请求的库
from ..utils import get_relevant_images, extract_title  # 正经注释：导入图片和标题提取工具函数 / 大白话注释：从工具箱里拿找图片和提取标题的工具

class WebBaseLoaderScraper:
    """
    【正经注释】基于 LangChain WebBaseLoader 的网页爬虫类，使用 LangChain 的文档加载器
    获取网页内容，同时通过 BeautifulSoup 提取相关图片和标题。

    【大白话注释】用 LangChain 的 WebBaseLoader 抓网页的爬虫。先用 WebBaseLoader 拿文字，
    再用 BeautifulSoup 补充提取图片和标题。比较简单，适合不需要 JavaScript 的普通网页。
    """

    def __init__(self, link, session=None):
        self.link = link  # 正经注释：存储待抓取的 URL / 大白话注释：记住要抓的网址
        self.session = session or requests.Session()  # 正经注释：存储或创建 HTTP 会话对象 / 大白话注释：有会话就用，没有就新建一个

    def scrape(self) -> tuple:
        """
        【正经注释】使用 LangChain WebBaseLoader 加载网页文档并拼接所有页面的文本内容，
        同时通过 HTTP 请求获取原始 HTML 以提取图片和标题。禁用 SSL 验证以提高兼容性。

        Returns:
            tuple: (content, image_urls, title) 拼接的文本内容、图片列表和标题；
                   异常时返回 ("", [], "")

        【大白话注释】开始抓网页！用 LangChain 的 WebBaseLoader 把网页内容加载进来，
        把所有文档的文字拼在一起。然后再用 BeautifulSoup 把图片和标题找出来。
        出错了就返回空结果。
        """
        try:
            from langchain_community.document_loaders import WebBaseLoader  # 正经注释：延迟导入 WebBaseLoader / 大白话注释：用到才导入
            loader = WebBaseLoader(self.link)  # 正经注释：创建 WebBaseLoader 实例 / 大白话注释：用这个网址创建加载器
            loader.requests_kwargs = {"verify": False}  # 正经注释：禁用 SSL 证书验证，提高兼容性 / 大白话注释：不验证 SSL 证书，有些网站证书有问题也能抓
            docs = loader.load()  # 正经注释：加载网页文档 / 大白话注释：把网页内容读进来
            content = ""  # 正经注释：初始化内容字符串 / 大白话注释：准备一个空字符串来装内容

            for doc in docs:  # 正经注释：遍历所有加载的文档，拼接内容 / 大白话注释：把每段文字拼在一起
                content += doc.page_content

            response = self.session.get(self.link)  # 正经注释：发送 HTTP 请求获取原始 HTML / 大白话注释：再请求一次拿原始 HTML（找图片和标题用）
            soup = BeautifulSoup(response.content, 'html.parser')  # 正经注释：解析 HTML / 大白话注释：解析 HTML
            image_urls = get_relevant_images(soup, self.link)  # 正经注释：提取相关图片 / 大白话注释：找有用的图片

            # Extract the title using the utility function
            # 正经注释：使用工具函数提取页面标题 / 大白话注释：拿到标题
            title = extract_title(soup)

            return content, image_urls, title  # 正经注释：返回内容、图片列表和标题 / 大白话注释：把结果打包返回

        except Exception as e:  # 正经注释：捕获所有异常并返回空结果 / 大白话注释：出错了就返回空的
            print("Error! : " + str(e))
            return "", [], ""
