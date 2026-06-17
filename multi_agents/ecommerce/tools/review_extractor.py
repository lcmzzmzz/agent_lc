"""
评论洞察抽取工具。

【正经注释】
从标准化数据源的 snippet/content 中，按句子切分并匹配抱怨类关键词，
抽取候选痛点句子。这是 ReviewInsightAgent 的基础工具，
MVP 阶段用关键词规则，后续可替换为 LLM 抽取。

【大白话注释】
把搜到的资料切成一句一句，挑出"抱怨/差评"相关的句子，
作为用户痛点分析的素材。
"""

from __future__ import annotations

import re

from multi_agents.ecommerce.state import EcommerceSource

# 抱怨/痛点相关关键词（小写匹配）
COMPLAINT_KEYWORDS = [
    "complain",
    "complaint",
    "negative",
    "bad",
    "poor",
    "leak",
    "leaks",
    "broken",
    "difficult",
    "hard to",
    "noise",
    "noisy",
    "battery",
    "refund",
    "return",
    "disappointed",
    "fail",
    "cheap",
    "stopped working",
]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。！？])\s+")


def split_sentences(text: str) -> list[str]:
    """按中英文句末标点切分句子。"""
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [part.strip() for part in parts if part.strip()]


def extract_review_insights(sources: list[EcommerceSource], limit: int = 12) -> list[str]:
    """从 sources 中抽取含抱怨关键词的句子，最多 limit 条（按句子去重）。"""
    insights: list[str] = []
    seen: set[str] = set()

    for source in sources:
        text = f"{source.get('snippet', '')} {source.get('content', '')}"
        for sentence in split_sentences(text):
            lower = sentence.lower()
            if any(keyword in lower for keyword in COMPLAINT_KEYWORDS):
                if sentence in seen:
                    continue
                seen.add(sentence)
                insights.append(sentence)
                if len(insights) >= limit:
                    return insights

    return insights
