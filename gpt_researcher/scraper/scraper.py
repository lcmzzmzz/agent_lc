"""
【正经注释】Web 爬虫核心调度模块，提供 Scraper 类，根据 URL 类型自动选择合适的爬虫后端
（BeautifulSoup、PyMuPDF、Browser、Arxiv、TavilyExtract、FireCrawl 等）进行内容提取，
支持异步并发抓取和自动去重。

【大白话注释】这个文件是爬虫系统的"总调度中心"，你给它一堆网址，它会自动判断每个网址该用
哪个爬虫去抓——PDF 用 PyMuPDF，学术论文用 Arxiv，普通网页用 BeautifulSoup 等等，
还会自动去重、并发抓取，省时省力。
"""

import asyncio  # 正经注释：提供异步 I/O 支持，用于并发抓取多个 URL / 大白话注释：Python 异步编程库，让多个网页可以同时抓
import importlib  # 正经注释：动态导入模块，用于运行时检测和安装依赖包 / 大白话注释：用来在程序跑起来的时候动态检查某个包有没有装
import logging  # 正经注释：日志记录模块，用于输出运行时信息 / 大白话注释：记录程序运行日志，方便排查问题
import subprocess  # 正经注释：子进程管理模块，用于自动 pip 安装缺失的依赖 / 大白话注释：用来在代码里自动执行 pip install 命令
import sys  # 正经注释：系统相关模块，获取当前 Python 解释器路径 / 大白话注释：获取当前用的是哪个 Python，装包的时候要用

import requests  # 正经注释：HTTP 请求库，用于创建和管理网络会话 / 大白话注释：发网络请求用的库，抓网页必须得有
from colorama import Fore, init  # 正经注释：终端彩色输出库，用于美化控制台提示信息 / 大白话注释：让终端输出的字带颜色，好看一点

from gpt_researcher.utils.workers import WorkerPool  # 正经注释：导入工作线程池，用于控制并发抓取的线程数 / 大白话注释：导入线程池工具，控制同时开几个线程去抓

from . import (  # 正经注释：从当前包导入所有可用的爬虫后端实现类 / 大白话注释：把工具箱里的各种爬虫都拿过来
    ArxivScraper,  # 正经注释：Arxiv 学术论文爬虫 / 大白话注释：抓学术论文的
    BeautifulSoupScraper,  # 正经注释：BeautifulSoup HTML 解析爬虫 / 大白话注释：用 BeautifulSoup 抓普通网页的
    BrowserScraper,  # 正经注释：Selenium 浏览器爬虫 / 大白话注释：开浏览器去抓的
    FireCrawl,  # 正经注释：FireCrawl API 爬虫 / 大白话注释：用 FireCrawl 服务的
    NoDriverScraper,  # 正经注释：zendriver 无驱动浏览器爬虫 / 大白话注释：偷偷开浏览器抓的
    PyMuPDFScraper,  # 正经注释：PyMuPDF PDF 解析爬虫 / 大白话注释：解析 PDF 文件的
    TavilyExtract,  # 正经注释：Tavily API 内容提取爬虫 / 大白话注释：用 Tavily 服务的
    WebBaseLoaderScraper,  # 正经注释：LangChain WebBaseLoader 爬虫 / 大白话注释：用 LangChain 加载网页的
)


class Scraper:
    """
    【正经注释】爬虫调度管理类，负责根据 URL 列表自动选择合适的爬虫后端进行内容提取，
    支持异步并发、URL 去重、依赖自动检测与安装等功能。

    【大白话注释】这就是爬虫的"总管"，你把一堆网址给它，它帮你把每个网址的内容都抓回来，
    自动去重，自动选合适的爬虫，还支持并发抓取提高效率。
    """

    def __init__(self, urls, user_agent, scraper, worker_pool: WorkerPool):
        """
        初始化 Scraper 类。
        Args:
            urls: 待抓取的 URL 列表（会自动去除重复项）
            user_agent: HTTP 请求的 User-Agent 标识
            scraper: 默认使用的爬虫类型名称
            worker_pool: 工作线程池，控制并发度
        """
        # Optimization: Remove duplicate URLs to avoid redundant scraping
        # 正经注释：使用 dict.fromkeys 去重，保持原始顺序不变 / 大白话注释：把重复的网址去掉，省得同一个网页抓两遍
        unique_urls = list(dict.fromkeys(urls))  # Preserves order while removing duplicates
        duplicates_removed = len(urls) - len(unique_urls)

        self.urls = unique_urls  # 正经注释：存储去重后的 URL 列表 / 大白话注释：记住要去抓的网址们
        self.session = requests.Session()  # 正经注释：创建 HTTP 会话对象，复用连接 / 大白话注释：开一个 HTTP 会话，抓多个网页可以复用连接
        self.session.headers.update({"User-Agent": user_agent})  # 正经注释：设置请求头中的 User-Agent / 大白话注释：伪装一下请求头，让网站以为你是正常浏览器
        self.scraper = scraper  # 正经注释：记录默认爬虫类型 / 大白话注释：记住默认用哪个爬虫
        if self.scraper == "tavily_extract":  # 正经注释：如果使用 Tavily 爬虫，检查其依赖是否已安装 / 大白话注释：如果选了 Tavily，先看看有没有装对应的包
            self._check_pkg(self.scraper)
        if self.scraper == "firecrawl":  # 正经注释：如果使用 FireCrawl 爬虫，检查其依赖是否已安装 / 大白话注释：如果选了 FireCrawl，先看看有没有装对应的包
            self._check_pkg(self.scraper)
        self.logger = logging.getLogger(__name__)  # 正经注释：初始化日志记录器 / 大白话注释：搞一个日志器，用来输出运行信息
        self.worker_pool = worker_pool  # 正经注释：存储工作线程池引用 / 大白话注释：记住线程池，控制并发用的

        # Log deduplication results if duplicates were found
        # 正经注释：如果有重复 URL 被移除，记录日志 / 大白话注释：如果去掉了重复网址，打印个日志告知一下
        if duplicates_removed > 0:
            self.logger.info(
                f"Removed {duplicates_removed} duplicate URL(s). "
                f"Scraping {len(unique_urls)} unique URLs instead of {len(urls)}."
            )

    async def run(self):
        """
        【正经注释】异步执行所有 URL 的内容抓取，使用 asyncio.gather 实现并发调度，
        最终过滤掉抓取失败（raw_content 为 None）的结果。

        【大白话注释】开始抓取所有网址的内容，多个网址同时抓，最后把没抓到的过滤掉。
        """
        contents = await asyncio.gather(  # 正经注释：并发执行所有 URL 的抓取任务 / 大白话注释：同时开干，一堆网址一起抓
            *(self.extract_data_from_url(url, self.session) for url in self.urls)
        )

        res = [content for content in contents if content["raw_content"] is not None]  # 正经注释：过滤掉抓取失败的结果 / 大白话注释：把没抓到内容的网址从结果里踢出去
        return res

    def _check_pkg(self, scrapper_name: str) -> None:
        """
        【正经注释】检查并确保所需的 Python 包已安装。如果缺失则尝试自动安装。
        当添加新爬虫到仓库时，需更新 pkg_map 映射表。

        Args:
            scrapper_name: 爬虫名称，用于在 pkg_map 中查找对应的包信息

        【大白话注释】看看需要的包装了没，没装就自动帮你 pip install 装上。
        目前只支持 tavily_extract 和 firecrawl 两个需要额外安装的爬虫。
        """
        pkg_map = {  # 正经注释：爬虫名称到包信息的映射表 / 大白话注释：一张对照表，记录哪个爬虫需要装哪个包
            "tavily_extract": {
                "package_installation_name": "tavily-python",  # 正经注释：pip 安装时使用的包名 / 大白话注释：pip install 后面跟的名字
                "import_name": "tavily",  # 正经注释：Python 导入时使用的模块名 / 大白话注释：代码里 import 的名字
            },
            "firecrawl": {
                "package_installation_name": "firecrawl-py",  # 正经注释：pip 安装时使用的包名 / 大白话注释：pip install 后面跟的名字
                "import_name": "firecrawl",  # 正经注释：Python 导入时使用的模块名 / 大白话注释：代码里 import 的名字
            },
        }
        pkg = pkg_map[scrapper_name]  # 正经注释：获取当前爬虫对应的包信息 / 大白话注释：查表，找到这个爬虫需要什么包
        if not importlib.util.find_spec(pkg["import_name"]):  # 正经注释：检测包是否已安装 / 大白话注释：看看这个包装了没有
            pkg_inst_name = pkg["package_installation_name"]
            init(autoreset=True)  # 正经注释：初始化 colorama 自动重置颜色 / 大白话注释：准备让终端输出带颜色
            print(Fore.YELLOW + f"{pkg_inst_name} not found. Attempting to install...")  # 正经注释：黄色提示包未找到，尝试安装 / 大白话注释：黄字提示：没找到这个包，正在尝试安装
            try:
                subprocess.check_call(  # 正经注释：通过子进程执行 pip install 命令 / 大白话注释：自动执行 pip install 装包
                    [sys.executable, "-m", "pip", "install", pkg_inst_name]
                )
                importlib.invalidate_caches()  # 正经注释：清除导入缓存，确保新安装的包能被发现 / 大白话注释：刷一下缓存，让 Python 知道新包装好了
                print(Fore.GREEN + f"{pkg_inst_name} installed successfully.")  # 正经注释：绿色提示安装成功 / 大白话注释：绿字提示：装好了！
            except subprocess.CalledProcessError:
                raise ImportError(  # 正经注释：安装失败时抛出 ImportError / 大白话注释：装不上就报错，让你手动装
                    Fore.RED
                    + f"Unable to install {pkg_inst_name}. Please install manually with "
                    f"`pip install -U {pkg_inst_name}`"
                )

    async def extract_data_from_url(self, link, session):
        """
        【正经注释】从单个 URL 提取内容数据，包含限流控制、日志记录和异常处理。
        如果爬虫支持异步接口（scrape_async）则直接调用，否则在线程池中执行同步方法。

        Args:
            link: 待抓取的 URL
            session: HTTP 会话对象

        Returns:
            dict: 包含 url、raw_content、image_urls、title 的结果字典

        【大白话注释】一个个网址去抓内容，先选个合适的爬虫，然后开始抓，
        抓到了就返回内容、图片和标题，抓不到就返回空。
        """
        async with self.worker_pool.throttle():  # 正经注释：通过工作池的限流器控制并发度 / 大白话注释：排队，别同时开太多去抓
            try:
                Scraper = self.get_scraper(link)  # 正经注释：根据 URL 获取合适的爬虫类 / 大白话注释：看看这个网址该用哪个爬虫
                scraper = Scraper(link, session)  # 正经注释：实例化爬虫对象 / 大白话注释：把选好的爬虫准备好

                # Get scraper name
                scraper_name = scraper.__class__.__name__  # 正经注释：获取爬虫类名用于日志 / 大白话注释：看看这个爬虫叫什么名字
                self.logger.info(f"\n=== Using {scraper_name} ===")

                # Get content
                if hasattr(scraper, "scrape_async"):  # 正经注释：如果爬虫支持异步接口则直接异步调用 / 大白话注释：如果这个爬虫支持异步，就用异步方式抓
                    content, image_urls, title = await scraper.scrape_async()
                else:  # 正经注释：否则将同步方法提交到线程池执行 / 大白话注释：不支持异步就把同步方法丢到线程池里跑
                    (
                        content,
                        image_urls,
                        title,
                    ) = await asyncio.get_running_loop().run_in_executor(
                        self.worker_pool.executor, scraper.scrape
                    )

                if len(content) < 100:  # 正经注释：内容过短时记录警告并返回空结果 / 大白话注释：抓到的内容太少了，可能没抓到有用的东西
                    self.logger.warning(f"Content too short or empty for {link}")
                    return {
                        "url": link,
                        "raw_content": None,
                        "image_urls": [],
                        "title": title,
                    }

                # Log results
                # 正经注释：记录抓取结果的关键信息 / 大白话注释：打印一下抓到了什么
                self.logger.info(f"\nTitle: {title}")
                self.logger.info(
                    f"Content length: {len(content) if content else 0} characters"
                )
                self.logger.info(f"Number of images: {len(image_urls)}")
                self.logger.info(f"URL: {link}")
                self.logger.info("=" * 50)

                if not content or len(content) < 100:  # 正经注释：二次检查内容是否有效 / 大白话注释：再确认一次，内容真的太短了就放弃
                    self.logger.warning(f"Content too short or empty for {link}")
                    return {
                        "url": link,
                        "raw_content": None,
                        "image_urls": [],
                        "title": title,
                    }

                return {  # 正经注释：返回成功抓取的结果 / 大白话注释：抓到了！返回内容、图片和标题
                    "url": link,
                    "raw_content": content,
                    "image_urls": image_urls,
                    "title": title,
                }

            except Exception as e:  # 正经注释：捕获所有异常，记录错误并返回空结果 / 大白话注释：出了什么错就记下来，别让整个程序崩了
                self.logger.error(f"Error processing {link}: {str(e)}")
                return {"url": link, "raw_content": None, "image_urls": [], "title": ""}

    def get_scraper(self, link):
        """
        【正经注释】根据 URL 特征（文件后缀、域名）或配置的默认爬虫类型，
        从爬虫映射表中查找并返回对应的爬虫类。

        Args:
            link: 待判断的 URL 链接

        Returns:
            type: 匹配到的爬虫类

        【大白话注释】看看这个链接是 PDF 还是学术论文还是普通网页，然后返回合适的爬虫类。
        .pdf 结尾的用 PyMuPDF，arxiv.org 的用 Arxiv 爬虫，其他的用默认配置的爬虫。
        """

        SCRAPER_CLASSES = {  # 正经注释：爬虫类型名称到爬虫类的映射字典 / 大白话注释：一张表，根据名字找对应的爬虫
            "pdf": PyMuPDFScraper,
            "arxiv": ArxivScraper,
            "bs": BeautifulSoupScraper,
            "web_base_loader": WebBaseLoaderScraper,
            "browser": BrowserScraper,
            "nodriver": NoDriverScraper,
            "tavily_extract": TavilyExtract,
            "firecrawl": FireCrawl,
        }

        scraper_key = None  # 正经注释：初始化爬虫类型键值 / 大白话注释：先清空，等会判断用哪个

        if link.endswith(".pdf"):  # 正经注释：PDF 文件使用 PyMuPDF 爬虫 / 大白话注释：链接以 .pdf 结尾？那是 PDF 文件
            scraper_key = "pdf"
        elif "arxiv.org" in link:  # 正经注释：arxiv.org 域名使用 Arxiv 爬虫 / 大白话注释：链接里有 arxiv.org？那是学术论文
            scraper_key = "arxiv"
        else:
            scraper_key = self.scraper  # 正经注释：其他情况使用配置的默认爬虫 / 大白话注释：都不是？那就用默认的爬虫

        scraper_class = SCRAPER_CLASSES.get(scraper_key)  # 正经注释：从映射表中查找对应的爬虫类 / 大白话注释：去表里找找这个键对应的爬虫
        if scraper_class is None:  # 正经注释：如果找不到对应爬虫则抛出异常 / 大白话注释：找不到？那就报错，没这种爬虫
            raise Exception("Scraper not found.")

        return scraper_class
