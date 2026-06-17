"""
【正经注释】HTML 处理辅助模块，提供超链接提取和格式化功能，
将 BeautifulSoup 解析后的 HTML 锚点标签转换为可读的链接列表。

【大白话注释】这个文件专门处理网页里的链接——把 HTML 里的 <a> 标签都找出来，
提取链接文字和 URL，还能把它们格式化成好看的文本格式。
"""
from __future__ import annotations  # 正经注释：启用延迟类型注解评估 / 大白话注释：让类型标注更好用

from bs4 import BeautifulSoup  # 正经注释：HTML 解析库 / 大白话注释：解析 HTML 的工具
from requests.compat import urljoin  # 正经注释：URL 拼接工具，处理相对路径转绝对路径 / 大白话注释：把相对网址拼成完整网址


def extract_hyperlinks(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    """
    【正经注释】从 BeautifulSoup 对象中提取所有超链接，返回 (链接文本, 绝对URL) 元组列表。

    Args:
        soup (BeautifulSoup): 已解析的 BeautifulSoup 对象
        base_url (str): 基础 URL，用于将相对路径转换为绝对路径

    Returns:
        List[Tuple[str, str]]: 提取的超链接列表，每个元素为 (文本, URL)

    【大白话注释】找出页面里所有的 <a> 标签（超链接），把每个链接的文字和完整网址都拿出来，
    返回一个列表，里面每个元素是 (链接文字, 完整网址) 这样的配对。
    """
    return [
        (link.text, urljoin(base_url, link["href"]))  # 正经注释：提取链接文本并用 urljoin 将 href 转为绝对 URL / 大白话注释：拿到链接文字和完整网址
        for link in soup.find_all("a", href=True)  # 正经注释：查找所有带 href 属性的 <a> 标签 / 大白话注释：找所有有网址的超链接
    ]


def format_hyperlinks(hyperlinks: list[tuple[str, str]]) -> list[str]:
    """
    【正经注释】将超链接元组列表格式化为可读的字符串列表，格式为 "文本 (URL)"。

    Args:
        hyperlinks (List[Tuple[str, str]]): 待格式化的超链接列表

    Returns:
        List[str]: 格式化后的字符串列表

    【大白话注释】把链接列表变成人能读的文字，比如 ("百度", "https://baidu.com")
    变成 "百度 (https://baidu.com)" 这样。
    """
    return [f"{link_text} ({link_url})" for link_text, link_url in hyperlinks]  # 正经注释：将每个链接格式化为 "文本 (URL)" 形式 / 大白话注释：把文字和网址拼成好看的格式
