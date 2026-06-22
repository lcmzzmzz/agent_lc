"""
数据源标准化。

【正经注释】
不同检索器（DuckDuckGo/Tavily/...）返回的键名不一致（href vs url、body vs snippet）。
normalize_source 把它们统一成 EcommerceSource 结构，并按 url/title 推断 source_type，
让后续 Agent 不再关心数据来源差异。

【大白话注释】
不同搜索引擎返回的"结果"长得不一样（有的叫 href，有的叫 url）。
这里把它们都整理成同一种格式，后面 Agent 拿到的就是整齐的数据。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from multi_agents.ecommerce.runtime.policy_guard import sanitize_source_url
from multi_agents.ecommerce.state import EcommerceSource


def infer_source_type(url: str, title: str = "") -> str:
    """根据 url 主机和 title 推断来源类型。

    用 urlparse().hostname 的域段判定，避免 "amazon." 子串误伤
    （如 not-amazon.reviews.com、fakeamazon.net 会被旧逻辑误判成 amazon）。
    """
    host = (urlparse(url).hostname or "").lower()
    parts = set(host.split("."))
    title_l = (title or "").lower()
    if "amazon" in parts:
        return "amazon"
    if "reddit" in parts:
        return "reddit"
    if "youtube" in parts or "tiktok" in parts:
        return "social"
    if "review" in title_l:
        return "review_site"
    return "blog"


def normalize_source(raw: dict[str, Any]) -> EcommerceSource:
    """把任意键名结构的原始结果转成统一 EcommerceSource。"""
    # 先算 url：title 的兜底链要用 url 主机名（Tavily 等检索器常不返回 title，
    # 用主机名兜底比 "Untitled source" 有辨识度，报告引用可读性更好）
    url = sanitize_source_url(
        str(raw.get("url") or raw.get("href") or raw.get("link") or "")
    )
    # title 兜底链：raw.title → raw.name → url 主机名（去 www 前缀）→ "Untitled source"
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    title = str(raw.get("title") or raw.get("name") or host or "Untitled source")
    snippet = str(
        raw.get("snippet") or raw.get("body") or raw.get("description") or ""
    )
    content = str(raw.get("content") or raw.get("page_content") or snippet)

    return {
        "title": title,
        "url": url,
        "source_type": infer_source_type(url, title),
        "snippet": snippet,
        "content": content,
    }
