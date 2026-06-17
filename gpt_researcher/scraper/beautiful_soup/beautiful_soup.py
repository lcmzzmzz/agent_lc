"""
【正经注释】基于 BeautifulSoup 的网页内容爬虫模块，通过 HTTP GET 请求获取网页 HTML，
使用 lxml 解析器解析，再经过标签清洗和文本提取得到纯净的正文内容、图片列表和标题。

【大白话注释】这个文件用 BeautifulSoup 来抓普通网页。流程就是：请求网页 -> 解析 HTML ->
删掉脚本和导航等没用的标签 -> 提取纯文字和图片 -> 返回结果。简单粗暴但好用。
"""
from bs4 import BeautifulSoup  # 正经注释：HTML 解析库，用于将 HTML 转为可操作的对象 / 大白话注释：解析 HTML 的主力工具
from urllib.parse import urljoin  # 正经注释：URL 拼接工具，处理相对路径 / 大白话注释：把相对网址拼成完整网址

from ..utils import get_relevant_images, extract_title, get_text_from_soup, clean_soup  # 正经注释：从父包导入爬虫通用工具函数 / 大白话注释：从工具箱里拿几个好用的工具——找图片、提取标题、提取文字、清洗 HTML

class BeautifulSoupScraper:
    """
    【正经注释】基于 BeautifulSoup 的网页爬虫类，通过 HTTP GET 请求获取网页内容，
    使用 lxml 解析器解析 HTML，清洗后提取正文、图片和标题信息。

    【大白话注释】用 BeautifulSoup 抓网页的爬虫，最基本的爬虫实现。
    发请求、解析 HTML、清洗掉没用的标签、提取文字和图片。
    """

    def __init__(self, link, session=None):
        self.link = link  # 正经注释：存储待抓取的 URL / 大白话注释：记住要抓的网址
        self.session = session  # 正经注释：存储 HTTP 会话对象，复用 TCP 连接 / 大白话注释：HTTP 会话，用来发网络请求

    def scrape(self):
        """
        【正经注释】执行网页内容抓取。通过 session 发送 GET 请求获取网页 HTML，
        使用 BeautifulSoup(lxml) 解析后，依次进行标签清洗、文本提取、图片筛选和标题提取。

        Returns:
            tuple: (content, image_urls, title) 正文内容、图片列表和标题；
                   异常时返回 ("", [], "")

        【大白话注释】开始抓网页！发请求拿到 HTML，解析它，把脚本和样式表等没用的标签删掉，
        然后提取纯文字、找出重要的图片、拿到网页标题，打包返回。
        出错了就返回空结果。
        """
        try:
            response = self.session.get(self.link, timeout=4)  # 正经注释：发送 GET 请求，超时 4 秒 / 大白话注释：去拿网页内容，最多等 4 秒
            soup = BeautifulSoup(  # 正经注释：使用 lxml 解析器创建 BeautifulSoup 对象 / 大白话注释：用 lxml 引擎解析 HTML
                response.content, "lxml", from_encoding=response.encoding
            )

            soup = clean_soup(soup)  # 正经注释：清洗 HTML，移除无关标签 / 大白话注释：删掉脚本、导航、广告等没用的东西

            content = get_text_from_soup(soup)  # 正经注释：从清洗后的 HTML 中提取纯文本 / 大白话注释：把 HTML 变成纯文字

            image_urls = get_relevant_images(soup, self.link)  # 正经注释：提取相关图片并按重要性排序 / 大白话注释：找出页面上有用的图片

            # Extract the title using the utility function
            # 正经注释：使用工具函数提取页面标题 / 大白话注释：拿到网页的标题
            title = extract_title(soup)

            return content, image_urls, title  # 正经注释：返回正文、图片列表和标题 / 大白话注释：把结果打包返回

        except Exception as e:  # 正经注释：捕获所有异常并打印错误信息 / 大白话注释：出错了就打印错误，返回空结果
            print("Error! : " + str(e))
            return "", [], ""
