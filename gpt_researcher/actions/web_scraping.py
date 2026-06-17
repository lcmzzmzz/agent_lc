"""网页抓取模块（Web Scraping）
【正经注释】
本模块提供 URL 批量抓取、URL 过滤和内容提取功能。
使用 Scraper 类执行实际抓取，WorkerPool 实现并发控制。
【大白话注释】
这个文件就是"爬虫调度器"——给它一堆链接，它就去抓内容。
"""
from typing import Any											# 正经注释：类型提示 / 大白话注释：类型标记
from colorama import Fore, Style								# 正经注释：终端彩色输出库 / 大白话注释：让报错信息变成红色

from gpt_researcher.utils.workers import WorkerPool				# 正经注释：工作线程池，控制并发数 / 大白话注释：控制"同时爬几个网页"的池子
from ..scraper import Scraper									# 正经注释：爬虫核心类 / 大白话注释：真正的爬虫
from ..config.config import Config								# 正经注释：配置类 / 大白话注释：读取设置
from ..utils.logger import get_formatted_logger					# 正经注释：格式化日志器 / 大白话注释：记事本

logger = get_formatted_logger()									# 正经注释：创建日志记录器 / 大白话注释：准备记事本


async def scrape_urls(											# 正经注释：批量抓取 URL 列表的异步函数 / 大白话注释：去抓一堆网页的内容
    urls, cfg: Config, worker_pool: WorkerPool
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    批量抓取 URL 内容
    【正经注释】创建 Scraper 实例并发抓取所有 URL，提取文本内容和图片 URL 列表。
    【大白话注释】给一堆链接，让爬虫去抓，返回抓到的内容和图片。
    Args:
        urls: URL 列表（大白话：要抓的网页链接）
        cfg: 配置对象（大白话：各种设置）
        worker_pool: 工作线程池（大白话：控制并发数）
    Returns:
        tuple: (抓取内容列表, 图片列表)（大白话：(抓到的文字, 找到的图片)）
    """
    scraped_data = []											# 正经注释：初始化抓取结果容器 / 大白话注释：准备装抓到的内容
    images = []													# 正经注释：初始化图片容器 / 大白话注释：准备装找到的图片
    user_agent = (												# 正经注释：设置 User-Agent，模拟浏览器访问 / 大白话注释：假装自己是浏览器
        cfg.user_agent
        if cfg
        else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    try:
        scraper = Scraper(urls, user_agent, cfg.scraper, worker_pool=worker_pool)	# 正经注释：创建 Scraper 实例 / 大白话注释：创建爬虫
        scraped_data = await scraper.run()						# 正经注释：异步执行抓取 / 大白话注释：开始爬！
        for item in scraped_data:								# 正经注释：从抓取结果中提取图片 URL / 大白话注释：看看每条结果里有没有图片
            if 'image_urls' in item:
                images.extend(item['image_urls'])				# 正经注释：收集所有图片 / 大白话注释：把图片存起来
    except Exception as e:
        print(f"{Fore.RED}Error in scrape_urls: {e}{Style.RESET_ALL}")	# 正经注释：红色输出错误信息 / 大白话注释：红色报错

    return scraped_data, images									# 正经注释：返回抓取内容和图片 / 大白话注释：把内容和图片交出去


async def filter_urls(urls: list[str], config: Config) -> list[str]:
    """
    根据配置过滤 URL
    【正经注释】排除配置中指定的域名（excluded_domains）。
    【大白话注释】把不想看的网站去掉。
    Args:
        urls: URL 列表（大白话：一堆链接）
        config: 配置对象（大白话：里面写了不要哪些网站）
    Returns:
        list[str]: 过滤后的 URL 列表（大白话：去掉不想看的之后的链接）
    """
    filtered_urls = []											# 正经注释：初始化过滤结果 / 大白话注释：准备装通过的链接
    for url in urls:											# 正经注释：遍历每个 URL / 大白话注释：一个一个检查
        # Add your filtering logic here						# 正经注释：检查 URL 是否包含任何排除域名 / 大白话注释：看看是不是"黑名单"里的网站
        if not any(excluded in url for excluded in config.excluded_domains):
            filtered_urls.append(url)							# 正经注释：不在排除列表中则保留 / 大白话注释：不在黑名单里就留着
    return filtered_urls										# 正经注释：返回过滤后的 URL / 大白话注释：交出去


async def extract_main_content(html_content: str) -> str:
    """
    从 HTML 中提取主要内容
    【正经注释】目前为占位实现，直接返回原始 HTML。
    【大白话注释】这个函数还没真正实现，现在就是把 HTML 原样返回。
    Args:
        html_content: 原始 HTML（大白话：网页代码）
    Returns:
        str: 提取的内容（大白话：目前还是原始 HTML）
    """
    # Implement content extraction logic here					# 正经注释：TODO - 需要用 BeautifulSoup 等库实现真正的正文提取 / 大白话注释：待实现——需要把广告、导航等去掉，只留正文
    return html_content											# 正经注释：当前直接返回原始 HTML / 大白话注释：原样返回


async def process_scraped_data(scraped_data: list[dict[str, Any]], config: Config) -> list[dict[str, Any]]:
    """
    处理抓取数据，提取并清洗主要内容
    【正经注释】对每条抓取结果检查状态，成功的提取正文，失败的保留原始数据。
    【大白话注释】把抓到的数据整理一下：成功的就提取正文，失败的就原样保留。
    Args:
        scraped_data: 抓取数据列表（大白话：爬虫抓回来的数据）
        config: 配置对象（大白话：各种设置）
    Returns:
        list[dict]: 处理后的数据列表（大白话：整理好的数据）
    """
    processed_data = []											# 正经注释：初始化处理结果 / 大白话注释：准备装整理好的数据
    for item in scraped_data:									# 正经注释：遍历每条抓取结果 / 大白话注释：一条一条处理
        if item['status'] == 'success':							# 正经注释：抓取成功的数据，提取正文 / 大白话注释：抓到了就提取正文
            main_content = await extract_main_content(item['content'])	# 正经注释：调用内容提取函数 / 大白话注释：提取正文
            processed_data.append({
                'url': item['url'],								# 正经注释：保留 URL / 大白话注释：来源链接
                'content': main_content,						# 正经注释：提取的正文内容 / 大白话注释：正文
                'status': 'success'								# 正经注释：标记状态为成功 / 大白话注释：标记"成功"
            })
        else:													# 正经注释：抓取失败的数据原样保留 / 大白话注释：没抓到就原样保留
            processed_data.append(item)
    return processed_data										# 正经注释：返回处理后的数据 / 大白话注释：交出去
