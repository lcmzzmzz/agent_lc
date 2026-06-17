"""
【正经注释】基于 Selenium WebDriver 的浏览器爬虫模块，通过控制真实浏览器实例
（Chrome/Firefox/Safari）加载网页，支持 Cookie 管理、页面滚动加载、
PDF 和 Arxiv 论文处理，适用于需要 JavaScript 渲染的动态网页。

【大白话注释】这个文件用 Selenium 开一个真浏览器来抓网页，能处理需要 JavaScript 才能显示内容的页面。
它会先去 Google 拿一下 Cookie（让网站觉得你是真人），然后去目标网页滚动到底部加载所有内容，
如果是 PDF 就用 PyMuPDF 解析，是 Arxiv 就用 Arxiv 工具抓，普通网页就用 BeautifulSoup 提取。
"""
from __future__ import annotations  # 正经注释：启用延迟类型注解评估，支持前向引用 / 大白话注释：让类型注解更好用，不用担心前后引用的问题

import traceback  # 正经注释：异常堆栈跟踪模块，用于获取完整的错误调用栈 / 大白话注释：出错了能打印完整的调用栈，方便找问题
import pickle  # 正经注释：对象序列化模块，用于保存和加载 Cookie / 大白话注释：把 Cookie 存到文件里，或者从文件里读出来
from pathlib import Path  # 正经注释：路径处理模块，跨平台的文件路径操作 / 大白话注释：处理文件路径用的
from sys import platform  # 正经注释：获取当前操作系统平台标识 / 大白话注释：看看当前是什么操作系统
import time  # 正经注释：时间模块，用于页面加载等待 / 大白话注释：让程序暂停等一等
import random  # 正经注释：随机数模块，用于生成随机字符串 / 大白话注释：生成随机字符串，给 Cookie 文件起名用
import string  # 正经注释：字符串常量模块，提供字母和数字字符集 / 大白话注释：提供英文字母和数字，配合 random 生成随机名
import os  # 正经注释：操作系统接口模块，用于文件删除等操作 / 大白话注释：用来删除 Cookie 临时文件

from bs4 import BeautifulSoup  # 正经注释：HTML 解析库 / 大白话注释：解析 HTML 的工具
from typing import Iterable, cast  # 正经注释：类型注解工具 / 大白话注释：类型标注用的

from .processing.scrape_skills import (scrape_pdf_with_pymupdf,  # 正经注释：导入 PDF 和 Arxiv 抓取辅助函数 / 大白话注释：导入解析 PDF 和 Arxiv 论文的小工具
                                       scrape_pdf_with_arxiv)

from urllib.parse import urljoin  # 正经注释：URL 拼接工具 / 大白话注释：拼网址用的

from ..utils import get_relevant_images, extract_title, get_text_from_soup, clean_soup  # 正经注释：导入爬虫通用工具函数 / 大白话注释：从工具箱里拿几个好用的工具

FILE_DIR = Path(__file__).parent.parent  # 正经注释：获取当前文件上两级目录的路径，用于定位 JS 脚本等资源 / 大白话注释：找到项目根目录的路径，后面要用来找 JS 文件

class BrowserScraper:
    """
    【正经注释】基于 Selenium WebDriver 的浏览器爬虫类，通过控制真实浏览器实例加载网页，
    支持 Cookie 管理（Google Cookie 获取、浏览器 Cookie 加载）、页面滚动加载、
    以及 PDF/Arxiv/普通网页的内容提取。

    【大白话注释】开一个真浏览器去抓网页的爬虫。比 BeautifulSoup 更强——能执行 JavaScript、
    能滚动页面加载更多内容、能处理 Cookie 验证。但也更慢、更占资源。
    """

    def __init__(self, url: str, session=None):
        self.url = url  # 正经注释：存储待抓取的 URL / 大白话注释：记住要抓的网址
        self.session = session  # 正经注释：存储 HTTP 会话对象 / 大白话注释：HTTP 会话
        self.selenium_web_browser = "chrome"  # 正经注释：默认使用 Chrome 浏览器 / 大白话注释：默认用 Chrome
        self.headless = False  # 正经注释：是否使用无头模式（默认显示浏览器窗口） / 大白话注释：默认显示浏览器窗口（调试时方便看）
        self.user_agent = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "  # 正经注释：设置 User-Agent 伪装为 Mac Chrome 浏览器 / 大白话注释：假装自己是 Mac 上的 Chrome 浏览器
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/128.0.0.0 Safari/537.36")
        self.driver = None  # 正经注释：Selenium WebDriver 实例，初始化时为 None / 大白话注释：浏览器驱动，还没创建
        self.use_browser_cookies = False  # 正经注释：是否加载本地浏览器的 Cookie / 大白话注释：要不要用你电脑上浏览器的 Cookie
        self._import_selenium()  # Import only if used to avoid unnecessary dependencies
        # 正经注释：仅在实例化时导入 Selenium，避免不需要时安装依赖 / 大白话注释：用到的时候才导入 Selenium，免得不用的也得装
        self.cookie_filename = f"{self._generate_random_string(8)}.pkl"  # 正经注释：生成随机文件名用于保存 Cookie / 大白话注释：给 Cookie 文件起个随机名，免得冲突

    def scrape(self) -> tuple:
        """
        【正经注释】执行浏览器爬虫的完整流程：初始化浏览器驱动 -> 获取 Google Cookie ->
        加载已保存的 Cookie -> 添加页面头 -> 抓取页面内容。

        Returns:
            tuple: (text, image_urls, title) 正文内容、图片列表和标题

        【大白话注释】开始抓网页！整个流程是：启动浏览器 -> 去 Google 拿个 Cookie（伪装成真人） ->
        加载之前存的 Cookie -> 给页面加个标识头 -> 抓内容 -> 关掉浏览器。最后一定要把浏览器关了。
        """
        if not self.url:  # 正经注释：检查 URL 是否已指定 / 大白话注释：没给网址？那就别干了
            print("URL not specified")
            return "A URL was not specified, cancelling request to browse website.", [], ""

        try:
            self.setup_driver()  # 正经注释：初始化浏览器驱动 / 大白话注释：启动浏览器
            self._visit_google_and_save_cookies()  # 正经注释：访问 Google 获取 Cookie / 大白话注释：先去 Google 走一趟，拿点 Cookie
            self._load_saved_cookies()  # 正经注释：加载已保存的 Cookie / 大白话注释：把之前存的 Cookie 也加载上
            self._add_header()  # 正经注释：向页面注入自定义头部 / 大白话注释：给页面加个标识头

            text, image_urls, title = self.scrape_text_with_selenium()  # 正经注释：使用 Selenium 抓取页面内容 / 大白话注释：开始正式抓网页内容
            return text, image_urls, title
        except Exception as e:  # 正经注释：捕获异常并返回错误信息 / 大白话注释：出错了就把错误信息返回
            print(f"An error occurred during scraping: {str(e)}")
            print("Full stack trace:")
            print(traceback.format_exc())
            return f"An error occurred: {str(e)}\n\nStack trace:\n{traceback.format_exc()}", [], ""
        finally:
            if self.driver:  # 正经注释：无论成功与否，最终都要关闭浏览器 / 大白话注释：不管成功还是失败，一定要把浏览器关了
                self.driver.quit()
            self._cleanup_cookie_file()  # 正经注释：清理临时 Cookie 文件 / 大白话注释：把临时 Cookie 文件删了，别占地方

    def _import_selenium(self):
        """
        【正经注释】动态导入 Selenium 相关模块，如果未安装则抛出 ImportError 并提供安装指引。

        【大白话注释】试着导入 Selenium 的各种组件。如果没装 Selenium，就告诉你怎么装。
        包括 WebDriver、等待条件、各种浏览器的选项类等等。
        """
        try:
            global webdriver, By, EC, WebDriverWait, TimeoutException, WebDriverException
            from selenium import webdriver  # 正经注释：Selenium WebDriver 核心模块 / 大白话注释：Selenium 的核心，用来控制浏览器
            from selenium.webdriver.common.by import By  # 正经注释：元素定位方式枚举 / 大白话注释：指定用哪种方式找页面元素（ID、CSS等）
            from selenium.webdriver.support import expected_conditions as EC  # 正经注释：预期条件类，用于等待页面元素 / 大白话注释：等待页面元素出现的条件
            from selenium.webdriver.support.wait import WebDriverWait  # 正经注释：显式等待工具 / 大白话注释：让程序等着，直到某个条件满足
            from selenium.common.exceptions import TimeoutException, WebDriverException  # 正经注释：Selenium 常见异常类 / 大白话注释：超时和 WebDriver 出错的异常

            global ChromeOptions, FirefoxOptions, SafariOptions
            from selenium.webdriver.chrome.options import Options as ChromeOptions  # 正经注释：Chrome 浏览器选项配置 / 大白话注释：Chrome 的设置项
            from selenium.webdriver.firefox.options import Options as FirefoxOptions  # 正经注释：Firefox 浏览器选项配置 / 大白话注释：Firefox 的设置项
            from selenium.webdriver.safari.options import Options as SafariOptions  # 正经注释：Safari 浏览器选项配置 / 大白话注释：Safari 的设置项
        except ImportError as e:  # 正经注释：导入失败时打印详细的安装指引 / 大白话注释：没装 Selenium 的话，告诉你怎么装
            print(f"Failed to import Selenium: {str(e)}")
            print("Please install Selenium and its dependencies to use BrowserScraper.")
            print("You can install Selenium using pip:")
            print("    pip install selenium")
            print("If you're using a virtual environment, make sure it's activated.")
            raise ImportError(
                "Selenium is required but not installed. See error message above for installation instructions.") from e

    def setup_driver(self) -> None:
        """
        【正经注释】根据配置的浏览器类型创建对应的 WebDriver 实例，设置 User-Agent、
        无头模式、JavaScript 启用等选项，Linux 环境下额外添加沙箱和调试端口参数。

        【大白话注释】配置并启动浏览器。可以选 Chrome、Firefox 或 Safari，
        设置好伪装的 User-Agent、是否无头模式等。Linux 上还会关闭沙箱模式。
        """

        options_available = {  # 正经注释：浏览器类型到选项类的映射 / 大白话注释：支持的三种浏览器
            "chrome": ChromeOptions,
            "firefox": FirefoxOptions,
            "safari": SafariOptions,
        }

        options = options_available[self.selenium_web_browser]()  # 正经注释：创建对应浏览器的选项实例 / 大白话注释：根据选的浏览器创建配置对象
        options.add_argument(f"user-agent={self.user_agent}")  # 正经注释：设置 User-Agent / 大白话注释：伪装浏览器身份
        if self.headless:  # 正经注释：如果启用无头模式则添加对应参数 / 大白话注释：如果不想显示浏览器窗口
            options.add_argument("--headless")
        options.add_argument("--enable-javascript")  # 正经注释：启用 JavaScript 支持 / 大白话注释：确保能执行 JS

        try:
            if self.selenium_web_browser == "firefox":  # 正经注释：创建 Firefox 驱动 / 大白话注释：用火狐浏览器
                self.driver = webdriver.Firefox(options=options)
            elif self.selenium_web_browser == "safari":  # 正经注释：创建 Safari 驱动 / 大白话注释：用 Safari 浏览器
                self.driver = webdriver.Safari(options=options)
            else:  # chrome / 正经注释：默认创建 Chrome 驱动 / 大白话注释：默认用 Chrome
                if platform == "linux" or platform == "linux2":  # 正经注释：Linux 环境下的特殊配置 / 大白话注释：Linux 上要额外配一些参数
                    options.add_argument("--disable-dev-shm-usage")  # 正经注释：禁用 /dev/shm 共享内存使用 / 大白话注释：防止 Linux 上内存不够用
                    options.add_argument("--remote-debugging-port=9222")  # 正经注释：设置远程调试端口 / 大白话注释：开一个调试端口
                options.add_argument("--no-sandbox")  # 正经注释：禁用沙箱模式 / 大白话注释：关闭沙箱，某些环境需要
                options.add_experimental_option("prefs", {"download_restrictions": 3})  # 正经注释：禁止浏览器下载文件 / 大白话注释：不让浏览器下载东西，安全点
                self.driver = webdriver.Chrome(options=options)

            if self.use_browser_cookies:  # 正经注释：如果配置了使用浏览器 Cookie 则加载 / 大白话注释：如果要用本地浏览器的 Cookie 就加载
                self._load_browser_cookies()

            # print(f"{self.selenium_web_browser.capitalize()} driver set up successfully.")
        except Exception as e:  # 正经注释：驱动创建失败时打印错误并向上抛出 / 大白话注释：浏览器启动失败就报错
            print(f"Failed to set up {self.selenium_web_browser} driver: {str(e)}")
            print("Full stack trace:")
            print(traceback.format_exc())
            raise

    def _load_saved_cookies(self):
        """
        【正经注释】从本地 pickle 文件加载之前保存的 Cookie，并注入到当前浏览器会话中。

        【大白话注释】从文件里读取之前存的 Cookie，放到当前浏览器里。
        这样浏览器就"记住"了之前的登录状态等信息。
        """
        cookie_file = Path(self.cookie_filename)  # 正经注释：构造 Cookie 文件路径 / 大白话注释：看看 Cookie 文件在哪
        if cookie_file.exists():  # 正经注释：如果文件存在则加载 / 大白话注释：文件在就加载
            cookies = pickle.load(open(self.cookie_filename, "rb"))  # 正经注释：反序列化读取 Cookie 列表 / 大白话注释：把 Cookie 从文件里读出来
            for cookie in cookies:
                self.driver.add_cookie(cookie)  # 正经注释：逐个添加 Cookie 到浏览器 / 大白话注释：把每个 Cookie 塞给浏览器
        else:
            print("No saved cookies found.")  # 正经注释：文件不存在时提示 / 大白话注释：没找到 Cookie 文件

    def _load_browser_cookies(self):
        """
        【正经注释】使用 browser_cookie3 库从本地浏览器（Chrome/Firefox）直接读取 Cookie，
        并注入到 Selenium 浏览器会话中。

        【大白话注释】直接从你电脑上的浏览器里"偷"Cookie，放到 Selenium 开的浏览器里。
        这样就能用你平时的登录状态去访问网页了。
        """
        try:
            import browser_cookie3  # 正经注释：导入浏览器 Cookie 提取库 / 大白话注释：这个库能直接读你浏览器里的 Cookie
        except ImportError:
            print(
                "browser_cookie3 is not installed. Please install it using: pip install browser_cookie3"
            )  # 正经注释：提示安装 browser_cookie3 / 大白话注释：没装就告诉你怎么装
            return

        if self.selenium_web_browser == "chrome":  # 正经注释：从 Chrome 读取 Cookie / 大白话注释：用 Chrome 的话就读 Chrome 的 Cookie
            cookies = browser_cookie3.chrome()
        elif self.selenium_web_browser == "firefox":  # 正经注释：从 Firefox 读取 Cookie / 大白话注释：用 Firefox 的话就读 Firefox 的 Cookie
            cookies = browser_cookie3.firefox()
        else:
            print(f"Cookie loading not supported for {self.selenium_web_browser}")  # 正经注释：不支持其他浏览器的 Cookie 加载 / 大白话注释：其他浏览器不支持读 Cookie
            return

        for cookie in cookies:
            self.driver.add_cookie({'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain})  # 正经注释：将浏览器 Cookie 添加到 Selenium 会话 / 大白话注释：把偷来的 Cookie 一个个塞进去

    def _cleanup_cookie_file(self):
        """
        【正经注释】删除之前保存的临时 Cookie 文件，释放磁盘空间。

        【大白话注释】把之前存 Cookie 的临时文件删掉，别留垃圾。
        """
        cookie_file = Path(self.cookie_filename)  # 正经注释：构造 Cookie 文件路径 / 大白话注释：找到 Cookie 文件
        if cookie_file.exists():  # 正经注释：文件存在则尝试删除 / 大白话注释：有就删
            try:
                os.remove(self.cookie_filename)
            except Exception as e:
                print(f"Failed to remove cookie file: {str(e)}")  # 正经注释：删除失败时打印错误 / 大白话注释：删不了就报个错
        else:
            print("No cookie file found to remove.")  # 正经注释：文件不存在时提示 / 大白话注释：本来就没有，不用删

    def _generate_random_string(self, length):
        """
        【正经注释】生成指定长度的随机字符串（由字母和数字组成），用于创建唯一的 Cookie 文件名。

        Args:
            length: 字符串长度

        Returns:
            str: 随机字符串

        【大白话注释】生成一串随机字母和数字，用来给 Cookie 文件起个不重复的名字。
        """
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def _get_domain(self):
        """
        【正经注释】从当前 URL 中提取域名，去除 'www.' 前缀。

        Returns:
            str: 域名字符串

        【大白话注释】从网址里把域名抠出来，去掉 www. 前缀。
        比如 https://www.example.com/page 变成 example.com。
        """
        from urllib.parse import urlparse

        """Get domain from URL, removing 'www' if present"""
        domain = urlparse(self.url).netloc  # 正经注释：从 URL 解析出网络位置（域名+端口） / 大白话注释：把域名部分拿出来
        return domain[4:] if domain.startswith("www.") else domain  # 正经注释：去除 www. 前缀 / 大白话注释：如果有 www. 就去掉

    def _visit_google_and_save_cookies(self):
        """
        【正经注释】先访问 Google 首页获取其 Cookie，保存到本地文件，
        用于后续访问目标网站时伪装为正常浏览器行为。

        【大白话注释】先去 Google 首页逛一圈，把 Google 给的 Cookie 存下来。
        这样后面去其他网站的时候，看起来就像是一个"正常使用过 Google 的真人浏览器"，
        不容易被反爬虫机制拦截。
        """
        try:
            self.driver.get("https://www.google.com")  # 正经注释：导航到 Google 首页 / 大白话注释：打开 Google
            time.sleep(2)  # Wait for cookies to be set / 正经注释：等待 2 秒确保 Cookie 设置完成 / 大白话注释：等两秒让 Cookie 生效

            # Save cookies to a file
            # 正经注释：将当前浏览器的所有 Cookie 序列化保存到文件 / 大白话注释：把 Cookie 存到文件里
            cookies = self.driver.get_cookies()
            pickle.dump(cookies, open(self.cookie_filename, "wb"))

            # print("Google cookies saved successfully.")
        except Exception as e:  # 正经注释：访问 Google 失败时打印错误但不中断流程 / 大白话注释：去 Google 失败了就算了，不影响后面
            print(f"Failed to visit Google and save cookies: {str(e)}")
            print("Full stack trace:")
            print(traceback.format_exc())

    def scrape_text_with_selenium(self) -> tuple:
        """
        【正经注释】使用 Selenium WebDriver 加载目标页面并提取内容。根据 URL 类型分别处理：
        PDF 文件使用 PyMuPDF 解析，Arxiv 链接使用 ArxivRetriever，普通网页使用 BeautifulSoup 解析。

        Returns:
            tuple: (text, image_urls, title) 正文、图片列表和标题

        【大白话注释】用浏览器打开目标网页，等待加载完成后，看看是什么类型的：
        是 PDF 就用 PyMuPDF 解析，是 Arxiv 论文就用 Arxiv 工具抓，
        是普通网页就用 BeautifulSoup 提取文字、图片和标题。
        """
        self.driver.get(self.url)  # 正经注释：导航到目标 URL / 大白话注释：打开要抓的网页

        try:
            WebDriverWait(self.driver, 20).until(  # 正经注释：显式等待 body 元素出现，最长等 20 秒 / 大白话注释：等网页加载，最多等 20 秒
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException as e:  # 正经注释：等待超时时返回提示信息 / 大白话注释：等了 20 秒还没加载出来，放弃
            print("Timed out waiting for page to load")
            print(f"Full stack trace:\n{traceback.format_exc()}")
            return "Page load timed out", [], ""

        self._scroll_to_bottom()  # 正经注释：滚动到页面底部以加载所有动态内容 / 大白话注释：滚到底部，让懒加载的内容都出来

        if self.url.endswith(".pdf"):  # 正经注释：PDF 文件使用 PyMuPDF 解析 / 大白话注释：是 PDF 的话用专门的 PDF 解析器
            text = scrape_pdf_with_pymupdf(self.url)
            return text, [], ""
        elif "arxiv" in self.url:  # 正经注释：Arxiv 链接使用 ArxivRetriever 获取内容 / 大白话注释：是 Arxiv 论文的话用专门的论文抓取工具
            doc_num = self.url.split("/")[-1]  # 正经注释：提取论文编号 / 大白话注释：从网址最后一段抠出论文编号
            text = scrape_pdf_with_arxiv(doc_num)
            return text, [], ""
        else:
            page_source = self.driver.execute_script(  # 正经注释：通过 JS 获取完整的页面 HTML / 大白话注释：用 JavaScript 把整个网页的 HTML 拿出来
                "return document.documentElement.outerHTML;"
            )
            soup = BeautifulSoup(page_source, "lxml")  # 正经注释：使用 lxml 解析 HTML / 大白话注释：解析 HTML

            soup = clean_soup(soup)  # 正经注释：清洗 HTML / 大白话注释：删掉没用的标签

            text = get_text_from_soup(soup)  # 正经注释：提取纯文本 / 大白话注释：拿到纯文字
            image_urls = get_relevant_images(soup, self.url)  # 正经注释：提取相关图片 / 大白话注释：拿到有用的图片
            title = extract_title(soup)  # 正经注释：提取标题 / 大白话注释：拿到标题

        return text, image_urls, title  # 正经注释：返回结果 / 大白话注释：把结果打包返回

    def _scroll_to_bottom(self):
        """
        【正经注释】循环滚动页面到底部，触发所有懒加载（lazy-load）内容加载，
        直到页面高度不再变化为止。

        【大白话注释】不停地往下滚页面，很多网站的内容是滚到才加载的，
        所以要滚到底确保所有内容都加载出来了。每滚一次等 2 秒让它加载。
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")  # 正经注释：获取当前页面总高度 / 大白话注释：看看页面有多高
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  # 正经注释：滚动到页面底部 / 大白话注释：滚到底
            time.sleep(2)  # Wait for content to load / 正经注释：等待 2 秒让内容加载 / 大白话注释：等两秒让它加载
            new_height = self.driver.execute_script("return document.body.scrollHeight")  # 正经注释：获取滚动后的页面高度 / 大白话注释：看看现在页面多高了
            if new_height == last_height:  # 正经注释：如果高度没变说明已到底 / 大白话注释：高度不变了？那到底了，不用再滚了
                break
            last_height = new_height  # 正经注释：更新高度继续下一轮 / 大白话注释：高度变了，继续滚

    def _scroll_to_percentage(self, ratio: float) -> None:
        """
        【正经注释】将页面滚动到指定百分比位置。

        Args:
            ratio: 滚动比例，范围 [0, 1]

        Raises:
            ValueError: 比例超出 [0, 1] 范围时抛出

        【大白话注释】滚到页面的某个百分比位置，比如 0.5 就是滚到中间。
        ratio 必须在 0 到 1 之间。
        """
        if ratio < 0 or ratio > 1:  # 正经注释：校验比例范围 / 大白话注释：比例不在 0-1 之间就报错
            raise ValueError("Percentage should be between 0 and 1")
        self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {ratio});")  # 正经注释：执行 JS 滚动到指定位置 / 大白话注释：滚到指定位置

    def _add_header(self) -> None:
        """
        【正经注释】通过执行 overlay.js 脚本在页面上添加自定义头部标识。

        【大白话注释】往网页里注入一段 JS，给页面加个自定义的头部显示。
        """
        self.driver.execute_script(open(f"{FILE_DIR}/browser/js/overlay.js", "r").read())  # 正经注释：读取并执行 overlay.js 脚本 / 大白话注释：读一个 JS 文件然后执行它
