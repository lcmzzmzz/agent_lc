"""浏览器管理技能模块（Browser Manager Skill）
【正经注释】
本模块提供 BrowserManager 类，负责网页抓取、内容提取和图片筛选。
通过 WorkerPool 控制并发抓取数，通过哈希去重避免重复图片。
【大白话注释】
这个文件就是"爬虫管理者"——负责调度爬虫去抓网页，还要挑出最好看的图片。
"""
from gpt_researcher.utils.workers import WorkerPool					# 正经注释：工作线程池 / 大白话注释：控制"同时爬几个网页"的池子

from ..actions.utils import stream_output								# 正经注释：WebSocket 输出流 / 大白话注释：给前端发消息
from ..actions.web_scraping import scrape_urls						# 正经注释：批量抓取函数 / 大白话注释：爬网页的函数
from ..scraper.utils import get_image_hash							# 正经注释：图片哈希工具 / 大白话注释：判断两张图片是不是一样的


class BrowserManager:
    """浏览器管理器——负责网页抓取和图片筛选

    【正经注释】
    管理研究过程中的网页抓取流程，包括：
    - URL 批量抓取和内容提取
    - 图片去重和筛选（基于内容哈希）
    - 进度推送（WebSocket）

    【大白话注释】
    这个类就是"爬虫管理者"：
    - 拿到一堆链接后，让爬虫去抓内容
    - 从抓到的图片里挑最好的几张
    - 每一步都告诉前端在干什么

    Attributes:
        researcher: 父级 GPTResearcher 实例（大白话：老板）
        worker_pool: 工作线程池（大白话：同时干活的爬虫数）
    """

    def __init__(self, researcher):
        """初始化浏览器管理器
        【正经注释】绑定父级 researcher 实例，创建受限于配置的 WorkerPool。
        【大白话注释】记住"老板"是谁，准备好爬虫池。
        Args:
            researcher: GPTResearcher 实例（大白话：老板）
        """
        self.researcher = researcher								# 正经注释：持有对父级实例的引用 / 大白话注释：记住老板
        self.worker_pool = WorkerPool(								# 正经注释：创建工作线程池，限制并发数和速率 / 大白话注释：创建爬虫池，控制同时爬几个、间隔多久
            researcher.cfg.max_scraper_workers,						# 正经注释：最大并发爬虫数 / 大白话注释：最多几个爬虫同时干活
            researcher.cfg.scraper_rate_limit_delay					# 正经注释：爬取间隔延迟 / 大白话注释：爬完一个等几秒再爬下一个
        )

    async def browse_urls(self, urls: list[str]) -> list[dict]:
        """批量抓取 URL 内容
        【正经注释】调用 scrape_urls 执行实际抓取，收集内容和图片，
        通过 select_top_images 筛选最相关的图片。
        【大白话注释】去抓一堆网页：先告诉前端"开始抓了"，然后让爬虫去抓，
        把抓到的内容和图片都存起来，图片还要挑最好的。
        Args:
            urls (list[str]): URL 列表（大白话：要抓的网页链接）
        Returns:
            list[dict]: 抓取的内容列表（大白话：抓到的内容）
        """
        if self.researcher.verbose:									# 正经注释：详细模式下推送抓取进度 / 大白话注释：开了"字幕"就告诉用户
            await stream_output(
                "logs",
                "scraping_urls",
                f"🌐 Scraping content from {len(urls)} URLs...",
                self.researcher.websocket,
            )

        scraped_content, images = await scrape_urls(				# 正经注释：调用批量抓取函数，返回内容和图片 / 大白话注释：让爬虫去抓，拿到文字和图片
            urls, self.researcher.cfg, self.worker_pool
        )
        self.researcher.add_research_sources(scraped_content)		# 正经注释：将抓取内容记录为研究来源 / 大白话注释：把抓到的内容存起来
        new_images = self.select_top_images(images, k=4)  # Select top 4 images	# 正经注释：从所有图片中筛选最相关的 4 张 / 大白话注释：挑最好的 4 张图
        self.researcher.add_research_images(new_images)				# 正经注释：将选中的图片添加到研究图片集合 / 大白话注释：把选中的图存起来

        if self.researcher.verbose:									# 正经注释：详细模式下推送抓取完成信息 / 大白话注释：开了"字幕"就汇报结果
            await stream_output(
                "logs",
                "scraping_content",
                f"📄 Scraped {len(scraped_content)} pages of content",
                self.researcher.websocket,
            )
            await stream_output(
                "logs",
                "scraping_images",
                f"🖼️ Selected {len(new_images)} new images from {len(images)} total images",
                self.researcher.websocket,
                True,
                new_images,
            )
            await stream_output(
                "logs",
                "scraping_complete",
                f"🌐 Scraping complete",
                self.researcher.websocket,
            )

        return scraped_content										# 正经注释：返回抓取的内容 / 大白话注释：把内容交出去

    def select_top_images(self, images: list[dict], k: int = 2) -> list[str]:
        """筛选最相关的图片并去重
        【正经注释】
        按相关度分数降序排列图片，通过内容哈希去重，
        排除已选过的图片，返回前 k 张的 URL。
        【大白话注释】
        从一堆图片里挑最好的：
        1. 按分数从高到低排
        2. 去掉重复的（内容一样的图）
        3. 去掉已经选过的
        4. 拿前 k 张
        Args:
            images (list[dict]): 图片字典列表，含 url 和 score（大白话：带分数的图片列表）
            k (int): 最多选几张（大白话：要几张）
        Returns:
            list[str]: 选中的图片 URL 列表（大白话：选中的图片链接）
        """
        unique_images = []											# 正经注释：去重后的图片列表 / 大白话注释：准备装选中的图片
        seen_hashes = set()											# 正经注释：已见哈希集合，用于内容去重 / 大白话注释：记下已经见过的图片"指纹"
        current_research_images = self.researcher.get_research_images()	# 正经注释：获取当前已有的研究图片 / 大白话注释：看看之前已经选了哪些图

        # Process images in descending order of their scores		# 正经注释：按分数从高到低处理图片 / 大白话注释：分高的先挑
        for img in sorted(images, key=lambda im: im["score"], reverse=True):	# 正经注释：降序排列 / 大白话注释：从最高分开始看
            img_hash = get_image_hash(img['url'])					# 正经注释：计算图片内容哈希 / 大白话注释：算一个"指纹"
            if (														# 正经注释：三个去重条件 / 大白话注释：检查能不能选这张图
                img_hash
                and img_hash not in seen_hashes						# 正经注释：哈希未见过（内容不重复） / 大白话注释：没见过的图片
                and img['url'] not in current_research_images		# 正经注释：URL 未被选中过 / 大白话注释：之前没选过的
            ):
                seen_hashes.add(img_hash)							# 正经注释：记录哈希 / 大白话注释：记下"指纹"
                unique_images.append(img["url"])					# 正经注释：添加到结果列表 / 大白话注释：选中这张图

                if len(unique_images) == k:							# 正经注释：达到数量上限则停止 / 大白话注释：够了就不挑了
                    break

        return unique_images										# 正经注释：返回选中的图片 URL 列表 / 大白话注释：把选好的图片交出去
