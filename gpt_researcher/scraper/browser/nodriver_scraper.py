"""
【正经注释】基于 zendriver 的无驱动浏览器爬虫模块，通过 CDP（Chrome DevTools Protocol）
直接控制 Chromium 内核浏览器，支持多浏览器实例池化管理、域名级速率限制、
页面滚动加载和异步并发抓取，适用于需要 JavaScript 渲染的高效场景。

【大白话注释】这个文件用 zendriver 来控制浏览器抓网页，比 Selenium 更轻量更快。
它有个"浏览器池"的设计——可以同时开着好几个浏览器标签页来抓，
还会自动控制访问同一个网站的速度（别太快被封），自动滚页面加载所有内容。
"""
from contextlib import asynccontextmanager  # 正经注释：异步上下文管理器工具，用于实现速率限制 / 大白话注释：用来写 async with 语句的工具
import math  # 正经注释：数学运算模块，用于向上取整超时时间 / 大白话注释：算数学用的
from pathlib import Path  # 正经注释：跨平台路径处理模块 / 大白话注释：处理文件路径
import random  # 正经注释：随机数模块，用于模拟人类行为的随机延迟 / 大白话注释：生成随机数，模拟人类操作的不规律
import traceback  # 正经注释：异常堆栈跟踪模块 / 大白话注释：打印完整的错误堆栈
from urllib.parse import urlparse  # 正经注释：URL 解析模块 / 大白话注释：拆解网址用的
from bs4 import BeautifulSoup  # 正经注释：HTML 解析库 / 大白话注释：解析 HTML 的工具
from typing import Dict, Literal, cast, Tuple, List  # 正经注释：类型注解工具 / 大白话注释：标注类型用的
import requests  # 正经注释：HTTP 请求库 / 大白话注释：发网络请求的库
import asyncio  # 正经注释：异步 I/O 模块 / 大白话注释：Python 异步编程核心库
import logging  # 正经注释：日志记录模块 / 大白话注释：记日志用的

from ..utils import get_relevant_images, extract_title, get_text_from_soup, clean_soup  # 正经注释：导入爬虫通用工具函数 / 大白话注释：从工具箱里拿工具


class NoDriverScraper:
    """
    【正经注释】基于 zendriver 的异步浏览器爬虫类，采用浏览器实例池化管理，
    支持域名级速率限制、负载均衡和自动扩缩容。

    【大白话注释】用 zendriver 控制浏览器的爬虫，核心设计是"浏览器池"——
    可以同时开多个浏览器（最多 5 个），每个浏览器可以开多个标签页（最多 8 个任务），
    自动分配最空闲的那个给你用，还会控制对同一个网站的访问频率。
    """
    logger = logging.getLogger(__name__)  # 正经注释：类级别的日志记录器 / 大白话注释：日志器，所有实例共用
    max_browsers = 5  # 正经注释：浏览器池最大实例数 / 大白话注释：最多同时开 5 个浏览器
    browser_load_threshold = 8  # 正经注释：单个浏览器的最大任务数阈值 / 大白话注释：一个浏览器最多同时处理 8 个任务，超了就再开新的
    browsers: set["NoDriverScraper.Browser"] = set()  # 正经注释：浏览器实例池，存储所有活跃的浏览器实例 / 大白话注释：所有正在用的浏览器都记在这里
    browsers_lock = asyncio.Lock()  # 正经注释：浏览器池操作锁，保证并发安全 / 大白话注释：一把锁，防止多个任务同时操作浏览器池

    @staticmethod
    def get_domain(url: str) -> str:
        """
        【正经注释】从 URL 中提取主域名，对于多级子域名只保留最后两级。

        Args:
            url: 完整的 URL 字符串

        Returns:
            str: 主域名（如 example.com）

        【大白话注释】从网址里提取域名部分，如果域名很长（比如 sub.api.example.com），
        就只保留最后两段（example.com）。
        """
        domain = urlparse(url).netloc  # 正经注释：提取 URL 的网络位置部分 / 大白话注释：把域名+端口部分拿出来
        parts = domain.split(".")  # 正经注释：按点分割域名 / 大白话注释：用 . 把域名切开
        if len(parts) > 2:  # 正经注释：超过两级的子域名只保留最后两级 / 大白话注释：域名段数太多就只留最后两段
            domain = ".".join(parts[-2:])
        return domain

    class Browser:
        """
        【正经注释】浏览器实例封装类，管理单个 zendriver 浏览器的标签页、速率限制、
        页面滚动和资源清理等操作。

        【大白话注释】一个浏览器实例的"管家"，负责打开页面、滚动加载内容、
        控制访问频率、关闭标签页等等。
        """
        def __init__(
            self,
            driver: "zendriver.Browser",
        ):
            self.driver = driver  # 正经注释：zendriver 浏览器实例 / 大白话注释：实际的浏览器对象
            self.processing_count = 0  # 正经注释：当前正在处理的任务计数 / 大白话注释：现在有几个任务在跑
            self.has_blank_page = True  # 正经注释：是否有空白页可用于新标签 / 大白话注释：浏览器刚打开时有个空白页，可以直接用
            self.allowed_requests_times = {}  # 正经注释：域名级请求时间记录（预留） / 大白话注释：记录每个域名上次访问时间
            self.domain_semaphores: Dict[str, asyncio.Semaphore] = {}  # 正经注释：域名级信号量字典，控制同一域名的并发 / 大白话注释：每个域名一把锁，防止同时访问同一个网站
            self.tab_mode = True  # 正经注释：是否使用标签页模式（而非新窗口） / 大白话注释：在新标签页打开，而不是新窗口
            self.max_scroll_percent = 500  # 正经注释：页面最大滚动百分比，防止无限滚动页面 / 大白话注释：最多滚 500%，防止那种无限滚动的页面
            self.stopping = False  # 正经注释：浏览器是否正在停止 / 大白话注释：标记浏览器是不是正在关

        async def get(self, url: str) -> "zendriver.Tab":
            """
            【正经注释】在浏览器中打开指定 URL，根据 tab_mode 决定使用新标签页或新窗口。
            成功时递增任务计数，异常时回滚。

            Args:
                url: 待打开的 URL

            Returns:
                zendriver.Tab: 打开的标签页对象

            【大白话注释】在浏览器里打开一个网页，默认在新标签页打开。
            如果出错了就把任务计数减回去。
            """
            self.processing_count += 1  # 正经注释：递增任务计数 / 大白话注释：又多了一个任务
            try:
                async with self.rate_limit_for_domain(url):  # 正经注释：进入域名速率限制 / 大白话注释：先排队，别访问太快
                    new_window = not self.has_blank_page  # 正经注释：如果没有空白页则需要新建窗口 / 大白话注释：第一次用空白页，之后都新建
                    self.has_blank_page = False  # 正经注释：标记空白页已使用 / 大白话注释：空白页用掉了
                    if self.tab_mode:  # 正经注释：标签页模式 / 大白话注释：在新标签页打开
                        return await self.driver.get(url, new_tab=new_window)
                    else:  # 正经注释：新窗口模式 / 大白话注释：在新窗口打开
                        return await self.driver.get(url, new_window=new_window)
            except Exception:
                self.processing_count -= 1  # 正经注释：异常时回滚任务计数 / 大白话注释：出错了就把计数减回去
                raise

        async def scroll_page_to_bottom(self, page: "zendriver.Tab"):
            """
            【正经注释】模拟人类滚动行为，分批次随机百分比向下滚动页面，
            触发懒加载内容加载，直到达到最大滚动百分比或页面底部。

            Args:
                page: zendriver 标签页对象

            【大白话注释】模拟人慢慢往下滚页面的动作，每次随机滚个 46%-97%，
            还会随机等一小会儿，就像真人在看一样。滚到页面底部或者滚够了就停。
            """
            total_scroll_percent = 0  # 正经注释：累计滚动百分比 / 大白话注释：记录一共滚了多少
            while True:
                # in tab mode, we need to bring the tab to front before scrolling to load the page content properly
                # 正经注释：标签页模式下需要先将标签页置于前台 / 大白话注释：多标签页时先把当前标签页切到前台
                if self.tab_mode:
                    await page.bring_to_front()
                scroll_percent = random.randrange(46, 97)  # 正经注释：随机生成 46%-96% 的滚动量 / 大白话注释：随机滚多少，模拟真人操作
                total_scroll_percent += scroll_percent
                await page.scroll_down(scroll_percent)  # 正经注释：执行向下滚动 / 大白话注释：往下滚
                await self.wait_or_timeout(page, "idle", 2)  # 正经注释：等待页面进入空闲状态 / 大白话注释：等页面加载完
                await page.sleep(random.uniform(0.23, 0.56))  # 正经注释：随机短暂延迟，模拟人类行为 / 大白话注释：随机等一小会儿，像真人一样

                if total_scroll_percent >= self.max_scroll_percent:  # 正经注释：超过最大滚动百分比则停止 / 大白话注释：滚够了就不滚了
                    break

                if cast(  # 正经注释：检测是否已滚动到页面底部 / 大白话注释：看看是不是到底了
                    bool,
                    await page.evaluate(
                        "window.innerHeight + window.scrollY >= document.scrollingElement.scrollHeight"
                    ),
                ):
                    break

        async def wait_or_timeout(
            self,
            page: "zendriver.Tab",
            until: Literal["complete", "idle"] = "idle",
            timeout: float = 3,
        ):
            """
            【正经注释】等待页面达到指定状态（complete 或 idle），超时后优雅退出不抛异常。

            Args:
                page: zendriver 标签页对象
                until: 等待目标状态，"complete" 为页面加载完成，"idle" 为空闲
                timeout: 超时时间（秒）

            【大白话注释】等页面加载，可以等"加载完成"或"空闲"状态。
            超时了也不报错，只是记录一下日志然后继续。
            """
            try:
                if until == "idle":  # 正经注释：等待页面空闲状态 / 大白话注释：等页面不忙了
                    await asyncio.wait_for(page.wait(), timeout)
                else:  # 正经注释：等待页面 complete 状态 / 大白话注释：等页面加载完
                    timeout = math.ceil(timeout)  # 正经注释：向上取整超时时间 / 大白话注释：超时时间取整
                    await page.wait_for_ready_state(until, timeout=timeout)
            except asyncio.TimeoutError:  # 正经注释：超时不抛异常，仅记录日志 / 大白话注释：等太久了就算了，不报错
                NoDriverScraper.logger.debug(
                    f"timeout waiting for {until} after {timeout} seconds"
                )

        async def close_page(self, page: "zendriver.Tab"):
            """
            【正经注释】关闭指定的标签页并递减任务计数。

            Args:
                page: 待关闭的标签页对象

            【大白话注释】关掉一个标签页，把任务计数减一。
            """
            try:
                await page.close()  # 正经注释：关闭标签页 / 大白话注释：关掉这个标签页
            except Exception as e:
                NoDriverScraper.logger.error(f"Failed to close page: {e}")  # 正经注释：关闭失败时记录错误 / 大白话注释：关不了就记一下
            finally:
                self.processing_count -= 1  # 正经注释：无论成功与否都递减任务计数 / 大白话注释：任务数减一

        @asynccontextmanager
        async def rate_limit_for_domain(self, url: str):
            """
            【正经注释】域名级速率限制上下文管理器，对同一域名的连续请求之间
            添加随机延迟，防止被目标网站的反爬机制封禁。

            Args:
                url: 待访问的 URL，用于提取域名

            【大白话注释】对同一个网站的访问加个"节流阀"，如果刚访问过这个网站，
            就等个 0.6-1.2 秒再访问，别太频繁被封号。
            """
            semaphore = None
            try:
                domain = NoDriverScraper.get_domain(url)  # 正经注释：提取 URL 主域名 / 大白话注释：看看是哪个网站

                semaphore = self.domain_semaphores.get(domain)  # 正经注释：查找该域名的信号量 / 大白话注释：看看这个网站有没有锁
                if not semaphore:  # 正经注释：如果没有则创建一个新的信号量 / 大白话注释：没有就创建一把
                    semaphore = asyncio.Semaphore(1)
                    self.domain_semaphores[domain] = semaphore

                was_locked = semaphore.locked()  # 正经注释：检查信号量是否被锁定 / 大白话注释：看看有没有别人在访问这个网站
                async with semaphore:
                    if was_locked:  # 正经注释：如果之前被锁定，添加随机延迟 / 大白话注释：有人在访问？那就等一会儿再去
                        await asyncio.sleep(random.uniform(0.6, 1.2))
                    yield

            except Exception as e:
                # Log error but don't block the request
                # 正经注释：记录错误但不阻塞请求 / 大白话注释：出错了记一下，但别影响正常抓取
                NoDriverScraper.logger.warning(
                    f"Rate limiting error for {url}: {str(e)}"
                )

        async def stop(self):
            """
            【正经注释】停止浏览器实例。使用 stopping 标志防止重复停止。

            【大白话注释】关掉这个浏览器。如果已经在关了就不重复操作。
            """
            if self.stopping:  # 正经注释：如果已经在停止中则直接返回 / 大白话注释：已经在关了就别再关了
                return
            self.stopping = True  # 正经注释：标记为正在停止 / 大白话注释：标记一下，开始关
            await self.driver.stop()  # 正经注释：停止 zendriver 浏览器 / 大白话注释：正式关浏览器

    @classmethod
    async def get_browser(cls, headless: bool = False) -> "NoDriverScraper.Browser":
        """
        【正经注释】从浏览器池中获取一个可用的浏览器实例。如果池为空则创建新实例；
        如果所有实例都满载且未达到上限则创建新实例；否则返回负载最低的实例。

        Args:
            headless: 是否使用无头模式

        Returns:
            Browser: 可用的浏览器实例

        【大白话注释】从浏览器池里拿一个浏览器来用。如果池子空了就创建新的，
        如果最空闲的浏览器也很忙了就再创建一个新的（最多 5 个），
        否则就用最空闲的那个。
        """
        async def create_browser():
            """
            【正经注释】创建新的 zendriver 浏览器实例并加入浏览器池。

            【大白话注释】真正创建浏览器的内部函数，启动 zendriver 并把它加到池子里。
            """
            try:
                global zendriver
                import zendriver  # 正经注释：延迟导入 zendriver / 大白话注释：用到才导入，省得不用的也要装
            except ImportError:
                raise ImportError(  # 正经注释：zendriver 未安装时抛出友好错误 / 大白话注释：没装 zendriver 就告诉你怎么装
                    "The zendriver package is required to use NoDriverScraper. "
                    "Please install it with: pip install zendriver"
                )

            config = zendriver.Config(  # 正经注释：配置 zendriver 浏览器参数 / 大白话注释：设置浏览器的参数
                headless=headless,  # 正经注释：无头模式配置 / 大白话注释：要不要显示浏览器窗口
                browser_connection_timeout=10,  # 正经注释：浏览器连接超时 10 秒 / 大白话注释：连浏览器最多等 10 秒
            )
            driver = await zendriver.start(config)  # 正经注释：启动 zendriver 浏览器 / 大白话注释：启动浏览器
            browser = cls.Browser(driver)  # 正经注释：创建 Browser 封装实例 / 大白话注释：包一层，方便管理
            cls.browsers.add(browser)  # 正经注释：加入浏览器池 / 大白话注释：记到池子里
            return browser

        async with cls.browsers_lock:  # 正经注释：加锁保护浏览器池操作 / 大白话注释：操作池子的时候锁一下，防止冲突
            if len(cls.browsers) == 0:  # 正经注释：池为空，创建新浏览器 / 大白话注释：一个浏览器都没有？那就创建一个
                # No browsers available, create new one
                return await create_browser()

            # Load balancing: Get browser with lowest number of tabs
            # 正经注释：负载均衡：选择任务数最少的浏览器 / 大白话注释：找最闲的那个浏览器
            browser = min(cls.browsers, key=lambda b: b.processing_count)

            # If all browsers are heavily loaded and we can create more
            # 正经注释：如果最空闲的浏览器也很忙，且未达到上限，则创建新浏览器 / 大白话注释：最闲的也很忙了？而且还没到上限？那就再开一个
            if (
                browser.processing_count >= cls.browser_load_threshold
                and len(cls.browsers) < cls.max_browsers
            ):
                return await create_browser()

            return browser

    @classmethod
    async def release_browser(cls, browser: Browser):
        """
        【正经注释】释放浏览器实例。当浏览器没有正在处理的任务时，停止并从池中移除。

        Args:
            browser: 待释放的浏览器实例

        【大白话注释】如果一个浏览器已经没有任务在跑了，就把它关掉并从池子里移除。
        如果还有任务在跑就先不关。
        """
        async with cls.browsers_lock:  # 正经注释：加锁保护浏览器池操作 / 大白话注释：操作池子的时候锁一下
            if browser and browser.processing_count <= 0:  # 正经注释：浏览器存在且没有正在处理的任务 / 大白话注释：浏览器在，而且没活干了
                try:
                    await browser.stop()  # 正经注释：停止浏览器 / 大白话注释：关掉它
                except Exception as e:
                    NoDriverScraper.logger.error(f"Failed to release browser: {e}")  # 正经注释：停止失败时记录错误 / 大白话注释：关不了就记一下
                finally:
                    cls.browsers.discard(browser)  # 正经注释：从池中移除浏览器 / 大白话注释：从池子里删掉

    def __init__(self, url: str, session: requests.Session | None = None):
        self.url = url  # 正经注释：存储待抓取的 URL / 大白话注释：记住要抓的网址
        self.session = session  # 正经注释：存储 HTTP 会话对象 / 大白话注释：HTTP 会话
        self.debug = False  # 正经注释：调试模式开关，开启时保存错误截图 / 大白话注释：调试模式，出问题时会截图保存

    async def scrape_async(self) -> Tuple[str, list[dict], str]:
        """
        【正经注释】异步执行网页内容抓取。从浏览器池获取实例 -> 打开页面 -> 等待加载 ->
        滚动到底部 -> 提取 HTML -> 解析并清洗 -> 返回文本、图片和标题。
        包含完善的资源清理机制（finally 块中关闭页面和释放浏览器）。

        Returns:
            Tuple[str, list[dict], str]: (正文内容, 图片列表, 页面标题)

        【大白话注释】开始异步抓网页！从浏览器池里借一个浏览器，打开目标网页，
        等它加载完，滚到底部让所有内容都出来，然后解析 HTML 提取文字、图片和标题。
        最后一定要把借的浏览器还回去（关标签页、释放浏览器）。
        """
        """Returns tuple of (text, image_urls, title)"""
        if not self.url:  # 正经注释：URL 为空时返回提示信息 / 大白话注释：没给网址就别干了
            return (
                "A URL was not specified, cancelling request to browse website.",
                [],
                "",
            )

        browser: NoDriverScraper.Browser | None = None
        page = None
        try:
            try:
                browser = await self.get_browser()  # 正经注释：从浏览器池获取一个实例 / 大白话注释：借一个浏览器
            except ImportError as e:  # 正经注释：zendriver 未安装时返回错误信息 / 大白话注释：没装 zendriver 就报错
                self.logger.error(f"Failed to initialize browser: {str(e)}")
                return str(e), [], ""

            page = await browser.get(self.url)  # 正经注释：在浏览器中打开目标 URL / 大白话注释：打开网页
            if page is None:  # 正经注释：页面打开失败（连接超时） / 大白话注释：页面没打开
                # browser.get() increments processing_count before returning;
                # a None result means the connection timed out. Decrement to
                # avoid leaking the slot and deadlocking the browser pool.
                # 正经注释：回滚任务计数，防止资源泄漏 / 大白话注释：之前计数加了一，现在得减回去，不然浏览器池会死锁
                browser.processing_count -= 1
                return "Browser failed to open page (returned None)", [], ""
            await browser.wait_or_timeout(page, "complete", 2)  # 正经注释：等待页面加载完成 / 大白话注释：等页面加载好
            # wait for potential redirection
            # 正经注释：等待可能的页面重定向完成 / 大白话注释：等一下看看会不会跳转到别的页面
            await page.sleep(random.uniform(0.3, 0.7))
            await browser.wait_or_timeout(page, "idle", 2)  # 正经注释：等待页面进入空闲状态 / 大白话注释：等页面不忙了

            await browser.scroll_page_to_bottom(page)  # 正经注释：滚动页面到底部加载所有内容 / 大白话注释：滚到底部
            html = await page.get_content()  # 正经注释：获取页面完整 HTML / 大白话注释：拿到整个网页的 HTML
            soup = BeautifulSoup(html, "lxml")  # 正经注释：使用 lxml 解析 HTML / 大白话注释：解析 HTML
            clean_soup(soup)  # 正经注释：清洗 HTML / 大白话注释：删掉没用的标签
            text = get_text_from_soup(soup)  # 正经注释：提取纯文本 / 大白话注释：拿到纯文字
            image_urls = get_relevant_images(soup, self.url)  # 正经注释：提取相关图片 / 大白话注释：拿到有用的图片
            title = extract_title(soup)  # 正经注释：提取标题 / 大白话注释：拿到标题

            if len(text) < 200:  # 正经注释：内容过短时记录警告 / 大白话注释：抓到的文字太少了，可能有问题
                self.logger.warning(
                    f"Content is too short from {self.url}. Title: {title}, Text length: {len(text)},\n"
                    f"excerpt: {text}."
                )
                if self.debug:  # 正经注释：调试模式下保存错误截图 / 大白话注释：调试模式就截个图，方便排查
                    screenshot_dir = Path("logs/screenshots")
                    screenshot_dir.mkdir(exist_ok=True)
                    screenshot_path = (
                        screenshot_dir
                        / f"screenshot-error-{NoDriverScraper.get_domain(self.url)}.jpeg"
                    )
                    await page.save_screenshot(screenshot_path)
                    self.logger.warning(
                        f"check screenshot at [{screenshot_path}] for more details."
                    )

            return text, image_urls, title  # 正经注释：返回抓取结果 / 大白话注释：把结果打包返回
        except Exception as e:  # 正经注释：捕获所有异常，记录完整错误信息 / 大白话注释：出错了就记下来
            self.logger.error(
                f"An error occurred during scraping: {str(e)}\n"
                "Full stack trace:\n"
                f"{traceback.format_exc()}"
            )
            return str(e), [], ""
        finally:
            try:
                if page and browser:  # 正经注释：关闭页面标签 / 大白话注释：如果页面还开着就关掉
                    await browser.close_page(page)
                if browser:  # 正经注释：释放浏览器实例回池 / 大白话注释：把浏览器还给池子
                    await self.release_browser(browser)
            except Exception as e:  # 正经注释：清理资源时的异常也记录 / 大白话注释：清理过程出错了也记一下
                self.logger.error(e)
