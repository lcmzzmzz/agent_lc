"""Shared helpers for ecommerce research-node content scoring."""

from __future__ import annotations

from typing import Any

from multi_agents.ecommerce.llm_helper import clamp


def format_sources_for_prompt(
    sources: list[dict[str, Any]], *, limit: int = 8, max_chars: int = 3000
) -> str:
    lines: list[str] = []
    for source in sources[:limit]:
        title = str(source.get("title") or "Untitled source")
        url = str(source.get("url") or "")
        snippet = str(source.get("snippet") or "")
        content = str(source.get("content") or "")
        lines.append(f"- title: {title}\n  url: {url}\n  text: {snippet} {content}")
    return "\n".join(lines)[:max_chars]


def format_review_texts_for_prompt(
    texts: list[str], *, limit: int = 12, max_chars: int = 3000
) -> str:
    return "\n".join(f"- {text}" for text in texts[:limit] if text)[:max_chars]


def coerce_score(data: dict | None, key: str, fallback: float) -> float:
    if not isinstance(data, dict):
        return fallback
    try:
        return clamp(data.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def coerce_confidence(data: dict | None, fallback: float) -> float:
    if not isinstance(data, dict):
        return fallback
    try:
        value = float(data.get("confidence", fallback))
    except (TypeError, ValueError):
        return fallback
    return round(max(0.0, min(0.9, value)), 2)


def coerce_string_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def coerce_competitors(
    value: Any, fallback: list[dict[str, str]], *, limit: int = 3
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return fallback
    competitors: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        positioning = str(item.get("positioning") or "").strip()
        if name:
            competitors.append({"name": name[:80], "positioning": positioning[:160]})
        if len(competitors) >= limit:
            break
    return competitors or fallback


def source_count_confidence(
    source_count: int, *, base: float = 0.35, step: float = 0.1
) -> float:
    return round(min(0.9, base + source_count * step), 2)


def rule_rationale(label: str) -> str:
    return f"LLM unavailable or returned invalid JSON; {label} estimated from simple rule fallback."
