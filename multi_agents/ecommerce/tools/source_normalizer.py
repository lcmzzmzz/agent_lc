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

from multi_agents.ecommerce.runtime.policy_guard import sanitize_source_url
from multi_agents.ecommerce.state import EcommerceSource


def infer_source_type(url: str, title: str = "") -> str:
    """根据 url 和 title 推断来源类型。"""
    text = f"{url} {title}".lower()
    if "amazon." in text:
        return "amazon"
    if "reddit." in text:
        return "reddit"
    if "youtube." in text or "tiktok." in text:
        return "social"
    if "review" in text:
        return "review_site"
    return "blog"


def normalize_source(raw: dict[str, Any]) -> EcommerceSource:
    """把任意键名结构的原始结果转成统一 EcommerceSource。"""
    title = str(raw.get("title") or raw.get("name") or "Untitled source")
    url = sanitize_source_url(
        str(raw.get("url") or raw.get("href") or raw.get("link") or "")
    )
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
