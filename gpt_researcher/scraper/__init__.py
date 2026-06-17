"""
【正经注释】scraper 包的初始化模块，负责统一导出所有爬虫（Scraper）类，
包括 BeautifulSoup、WebBaseLoader、Arxiv、PyMuPDF、Browser、NoDriver、TavilyExtract、FireCrawl 等，
供外部通过 from gpt_researcher.scraper import XxxScraper 方式使用。

【大白话注释】这个文件就是爬虫工具箱的"总入口"，把所有能用的爬虫都摆出来，
外面要哪个直接 import 就行，不用一个一个去找。
"""
from .beautiful_soup.beautiful_soup import BeautifulSoupScraper  # 正经注释：从 BeautifulSoup 子模块导入 BeautifulSoup 爬虫类 / 大白话注释：导入用 BeautifulSoup 库来抓网页的爬虫
from .web_base_loader.web_base_loader import WebBaseLoaderScraper  # 正经注释：从 WebBaseLoader 子模块导入基于 LangChain 的网页加载爬虫类 / 大白话注释：导入用 LangChain 的 WebBaseLoader 来抓网页的爬虫
from .arxiv.arxiv import ArxivScraper  # 正经注释：从 Arxiv 子模块导入 Arxiv 论文爬虫类 / 大白话注释：导入专门抓 Arxiv 学术论文的爬虫
from .pymupdf.pymupdf import PyMuPDFScraper  # 正经注释：从 PyMuPDF 子模块导入 PDF 文档爬虫类 / 大白话注释：导入专门解析 PDF 文件的爬虫
from .browser.browser import BrowserScraper  # 正经注释：从 Browser 子模块导入基于 Selenium 的浏览器爬虫类 / 大白话注释：导入用 Selenium 开浏览器来抓网页的爬虫
from .browser.nodriver_scraper import NoDriverScraper  # 正经注释：从 NoDriver 子模块导入基于 zendriver 的无驱动浏览器爬虫类 / 大白话注释：导入用 zendriver 偷偷开浏览器抓网页的爬虫（不需要 WebDriver）
from .tavily_extract.tavily_extract import TavilyExtract  # 正经注释：从 TavilyExtract 子模块导入基于 Tavily API 的内容提取爬虫类 / 大白话注释：导入用 Tavily API 远程提取网页内容的爬虫
from .firecrawl.firecrawl import FireCrawl  # 正经注释：从 FireCrawl 子模块导入基于 FireCrawl API 的内容提取爬虫类 / 大白话注释：导入用 FireCrawl 服务远程提取网页内容的爬虫
from .scraper import Scraper  # 正经注释：从当前包导入统一的爬虫调度管理类 / 大白话注释：导入爬虫的总调度器，它会根据链接类型自动选哪个爬虫

__all__ = [  # 正经注释：定义当前包对外公开的 API 名称列表 / 大白话注释：告诉大家这个工具箱里有哪些工具可以用
    "BeautifulSoupScraper",
    "WebBaseLoaderScraper",
    "ArxivScraper",
    "PyMuPDFScraper",
    "BrowserScraper",
    "NoDriverScraper",
    "TavilyExtract",
    "Scraper",
    "FireCrawl",
]
