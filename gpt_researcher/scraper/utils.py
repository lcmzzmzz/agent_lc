"""
【正经注释】Web 爬虫辅助工具模块，提供 HTML 内容提取、图片筛选与评分、标题提取、
HTML 清洗、文本格式化等通用函数，供各个爬虫后端复用。

【大白话注释】这个文件是所有爬虫共用的"工具箱"，里面有提取网页标题、找出重要图片、
清洗掉广告和导航栏、把 HTML 变成干净文字等各种好用的小工具函数。
"""

import hashlib  # 正经注释：哈希计算库，用于生成图片 URL 的唯一标识 / 大白话注释：用来给图片网址生成一个"指纹"，方便去重
import logging  # 正经注释：日志记录模块 / 大白话注释：记录日志用的
import re  # 正经注释：正则表达式库，用于文本清洗 / 大白话注释：用正则表达式处理文字
from urllib.parse import parse_qs, urljoin, urlparse  # 正经注释：URL 解析工具，处理链接拼接和参数提取 / 大白话注释：处理网址相关的东西——拼链接、拆参数

import bs4  # 正经注释：BeautifulSoup 核心库，用于 HTML 标签类型判断 / 大白话注释：BeautifulSoup 的核心，判断标签类型用的
from bs4 import BeautifulSoup  # 正经注释：HTML 解析库，将 HTML 转为可操作的树结构 / 大白话注释：把 HTML 网页变成好操作的对象


def get_relevant_images(soup: BeautifulSoup, url: str) -> list:
    """
    【正经注释】从 BeautifulSoup 对象中提取与页面内容相关的图片，根据 CSS 类名和尺寸属性
    进行评分排序，返回按相关性降序排列的图片列表（最多 10 张）。

    Args:
        soup: 已解析的 BeautifulSoup 对象
        url: 页面基础 URL，用于将相对路径转换为绝对路径

    Returns:
        list: 包含 {'url': str, 'score': int} 的图片列表，按分数降序

    【大白话注释】从网页里找出"有用的"图片，会根据图片的 class 名字和大小来打分——
    大图片和带 featured/hero/main 这些 class 的图片分数高，排在前面，最多返回 10 张。
    """
    image_urls = []

    try:
        # Find all img tags with src attribute
        # 正经注释：查找所有带有 src 属性的 img 标签 / 大白话注释：找到页面上所有有图片地址的 img 标签
        all_images = soup.find_all('img', src=True)

        for img in all_images:
            img_src = urljoin(url, img['src'])  # 正经注释：将相对路径转换为绝对 URL / 大白话注释：把相对地址拼成完整的网址
            if img_src.startswith(('http://', 'https://')):  # 正经注释：只保留 HTTP/HTTPS 协议的图片 / 大白话注释：只要正经的网络图片，不要 data: 之类的
                score = 0
                # Check for relevant classes
                # 正经注释：如果图片 class 包含关键特征词则给予高分 / 大白话注释：图片带有 header、featured、hero 这些 class？说明是重要图片，给高分
                if any(cls in img.get('class', []) for cls in ['header', 'featured', 'hero', 'thumbnail', 'main', 'content']):
                    score = 4  # Higher score
                # Check for size attributes
                # 正经注释：根据图片的宽高属性评估尺寸并给予相应分数 / 大白话注释：看看图片标注的尺寸有多大，越大分越高
                elif img.get('width') and img.get('height'):
                    width = parse_dimension(img['width'])
                    height = parse_dimension(img['height'])
                    if width and height:
                        if width >= 2000 and height >= 1000:
                            score = 3  # Medium score (very large images)
                        elif width >= 1600 or height >= 800:
                            score = 2  # Lower score
                        elif width >= 800 or height >= 500:
                            score = 1  # Lowest score
                        elif width >= 500 or height >= 300:
                            score = 0  # Lowest score
                        else:
                            continue  # Skip small images / 正经注释：跳过尺寸过小的图片 / 大白话注释：太小的图片直接跳过

                image_urls.append({'url': img_src, 'score': score})

        # Sort images by score (highest first)
        # 正经注释：按分数降序排列图片 / 大白话注释：按分数从高到低排，重要的图片排前面
        sorted_images = sorted(image_urls, key=lambda x: x['score'], reverse=True)

        return sorted_images[:10]  # Ensure we don't return more than 10 images in total
        # 正经注释：限制最多返回 10 张图片 / 大白话注释：最多给你 10 张图片，够用了

    except Exception as e:
        logging.error(f"Error in get_relevant_images: {e}")  # 正经注释：出错时记录错误日志并返回空列表 / 大白话注释：出错了就记一下，返回空的
        return []

def parse_dimension(value: str) -> int:
    """
    【正经注释】解析尺寸字符串值，支持带 'px' 后缀和浮点数格式，返回整数像素值。

    Args:
        value: 尺寸字符串（如 '1920px'、'409.12'）

    Returns:
        int: 解析后的像素值，解析失败返回 None

    【大白话注释】把类似 '1920px' 或 '409.12' 这样的尺寸字符串变成数字。
    比如 '1920px' 变成 1920，'409.12' 变成 409。
    """
    if value.lower().endswith('px'):  # 正经注释：去除 'px' 后缀 / 大白话注释：如果有 px 单位就去掉
        value = value[:-2]  # Remove 'px' suffix
    try:
        # Convert to float first to handle decimal values like '409.12'
        # 正经注释：先转为浮点数再取整，以处理带小数的值 / 大白话注释：先当小数处理，再变成整数，防止 '409.12' 这种值报错
        return int(float(value))
    except (ValueError, TypeError) as e:
        print(f"Error parsing dimension value {value}: {e}")  # 正经注释：解析失败时打印错误并返回 None / 大白话注释：转不了就报错，返回空
        return None

def extract_title(soup: BeautifulSoup) -> str:
    """
    【正经注释】从 BeautifulSoup 对象中提取页面标题（<title> 标签内容）。

    Args:
        soup: 已解析的 BeautifulSoup 对象

    Returns:
        str: 页面标题文本，无标题时返回空字符串

    【大白话注释】从网页里取出 <title> 标签的文字，就是浏览器标签栏上显示的那个标题。
    如果网页没写标题，就返回空字符串。
    """
    return soup.title.string if soup.title else ""

def get_image_hash(image_url: str) -> str:
    """
    【正经注释】基于图片文件名和关键查询参数计算 MD5 哈希值，用于图片去重。

    Args:
        image_url: 图片的完整 URL

    Returns:
        str: 32 位 MD5 哈希字符串，计算失败返回 None

    【大白话注释】给图片网址算一个"指纹"（哈希值），用来判断两张图片是不是同一张。
    主要是看文件名和 CDN 参数，不看完整的 URL，这样 CDN 地址不同但图片一样的也能识别出来。
    """
    try:
        parsed_url = urlparse(image_url)

        # Extract the filename
        # 正经注释：从 URL 路径中提取文件名 / 大白话注释：从网址里抠出文件名部分
        filename = parsed_url.path.split('/')[-1]

        # Extract essential query parameters (e.g., 'url' for CDN-served images)
        # 正经注释：提取关键查询参数（如 CDN 图片的 'url' 参数） / 大白话注释：看看网址参数里有没有 CDN 地址之类的关键信息
        query_params = parse_qs(parsed_url.query)
        essential_params = query_params.get('url', [])

        # Combine filename and essential parameters
        # 正经注释：将文件名和关键参数拼接为唯一标识 / 大白话注释：把文件名和关键参数拼在一起作为唯一标识
        image_identifier = filename + ''.join(essential_params)

        # Calculate hash
        # 正经注释：计算 MD5 哈希值 / 大白话注释：算出这个标识的 MD5 "指纹"
        return hashlib.md5(image_identifier.encode()).hexdigest()
    except Exception as e:
        logging.error(f"Error calculating image hash for {image_url}: {e}")  # 正经注释：计算失败时记录错误 / 大白话注释：算不出来就报错
        return None


def clean_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """
    【正经注释】清洗 BeautifulSoup 对象，移除 script、style、footer、header、nav、menu、sidebar、svg
    等与正文无关的标签，以及 class 包含 nav/menu/sidebar/footer 的标签。

    Args:
        soup: 已解析的 BeautifulSoup 对象

    Returns:
        BeautifulSoup: 清洗后的 BeautifulSoup 对象（原地修改）

    【大白话注释】把网页里跟正文无关的东西都删掉——导航栏、页脚、脚本、样式表、侧边栏等等，
    只留下正文内容。这样抓到的文字才干净，没有广告和乱七八糟的东西。
    """
    for tag in soup.find_all(  # 正经注释：查找并移除所有指定类型的标签 / 大白话注释：找到这些没用的标签然后删掉它们
        [
            "script",    # 正经注释：JavaScript 脚本 / 大白话注释：JS 代码
            "style",     # 正经注释：CSS 样式 / 大白话注释：样式表
            "footer",    # 正经注释：页脚 / 大白话注释：页面底部的页脚
            "header",    # 正经注释：页头 / 大白话注释：页面顶部的页头
            "nav",       # 正经注释：导航栏 / 大白话注释：导航栏
            "menu",      # 正经注释：菜单 / 大白话注释：菜单
            "sidebar",   # 正经注释：侧边栏 / 大白话注释：侧边栏
            "svg",       # 正经注释：SVG 图形 / 大白话注释：矢量图形
        ]
    ):
        tag.decompose()  # 正经注释：从 DOM 树中移除标签及其所有子节点 / 大白话注释：把这个标签连同它里面的东西都删了

    disallowed_class_set = {"nav", "menu", "sidebar", "footer"}  # 正经注释：不允许的 CSS 类名集合 / 大白话注释：这些 class 名字的标签也是没用的

    # clean tags with certain classes
    # 正经注释：定义辅助函数判断标签是否包含不允许的 class / 大白话注释：写个小函数看看标签有没有那些不让留下的 class
    def does_tag_have_disallowed_class(elem) -> bool:
        if not isinstance(elem, bs4.Tag):  # 正经注释：非标签元素直接返回 False / 大白话注释：不是 HTML 标签的跳过
            return False

        return any(
            cls_name in disallowed_class_set for cls_name in elem.get("class", [])
        )

    for tag in soup.find_all(does_tag_have_disallowed_class):  # 正经注释：查找并移除包含不允许 class 的标签 / 大白话注释：把带有这些 class 的标签也删了
        tag.decompose()

    return soup


def get_text_from_soup(soup: BeautifulSoup) -> str:
    """
    【正经注释】从 BeautifulSoup 对象中提取纯文本内容，使用换行符分隔并去除多余空白。

    Args:
        soup: 已清洗的 BeautifulSoup 对象

    Returns:
        str: 提取的纯文本内容

    【大白话注释】把清洗后的 HTML 变成纯文字，去掉所有标签，只留下能读的文字内容，
    还会把多余的空格合并成一个。
    """
    text = soup.get_text(strip=True, separator="\n")  # 正经注释：提取文本，strip=True 去除首尾空白，separator 用换行分隔 / 大白话注释：把 HTML 标签都去掉，只留文字
    # Remove excess whitespace
    # 正经注释：使用正则表达式将两个及以上的连续空白替换为单个空格 / 大白话注释：把一堆空格压成一个
    text = re.sub(r"\s{2,}", " ", text)
    return text
