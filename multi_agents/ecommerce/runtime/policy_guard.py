"""
运行时策略护栏。

【正经注释】
集中校验研究请求 / 工具权限 / URL 安全 / 敏感信息脱敏，
在 graph 跑起来之前把"明显违法"的输入挡掉，
避免无效请求浪费检索/LLM 调用，也防止内网或本地资源被误抓。

【大白话注释】
正式开跑前的"安检门"：
1. query / depth / market / platform 不合法 → 直接拒绝；
2. 某个 Agent 想用不该用的工具 → 直接拒绝；
3. URL 指向 file://、localhost、内网 IP → 当成空 URL；
4. 把 token / password 之类的字段统一涂黑，写日志/审计时不再泄露。
"""

from __future__ import annotations

import copy
import ipaddress
import re
from typing import Any
from urllib.parse import urlparse


ALLOWED_DEPTHS = {"fast", "standard", "deep"}
ALLOWED_MARKETS = {"US", "UK", "DE", "JP"}
ALLOWED_PLATFORMS = {"amazon", "google", "reddit", "tiktok", "youtube", "web"}
SECRET_KEY_PARTS = ("token", "api_key", "apikey", "authorization", "password", "secret")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([a-z0-9_]*(?:token|api_key|apikey|authorization|password|secret)[a-z0-9_]*)"
    r"\s*([=:])\s*([^\s,;]+)"
)

TOOL_PERMISSIONS = {
    "TrendResearchAgent": {"search"},
    "CompetitorAnalyzerAgent": {"search"},
    "ReviewInsightAgent": {"review_scrape", "search"},
    "OpportunityScoringAgent": {"llm", "rule_score"},
    "ReportWriterAgent": {"state_read", "markdown_write"},
    "QualityReviewerAgent": {"state_read", "quality_check"},
}


class PolicyViolation(ValueError):
    """请求 / 工具调用违反运行时策略时抛出。"""


def validate_research_request(
    *,
    query: str,
    target_market: str,
    platforms: list[str] | None,
    depth: str,
) -> None:
    """校验单次研究请求的基础约束；不通过抛 PolicyViolation。"""
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        raise PolicyViolation("query must not be empty")
    if len(cleaned_query) > 200:
        raise PolicyViolation("query must be 200 characters or fewer")
    if depth not in ALLOWED_DEPTHS:
        raise PolicyViolation(f"depth must be one of {sorted(ALLOWED_DEPTHS)}")
    if target_market not in ALLOWED_MARKETS:
        raise PolicyViolation(f"target_market must be one of {sorted(ALLOWED_MARKETS)}")
    invalid_platforms = [p for p in (platforms or []) if p not in ALLOWED_PLATFORMS]
    if invalid_platforms:
        raise PolicyViolation(f"unsupported platforms: {invalid_platforms}")


def assert_tool_allowed(agent: str, tool: str) -> None:
    """检查某个 Agent 是否有权使用某个工具；越权抛 PolicyViolation。"""
    allowed = TOOL_PERMISSIONS.get(agent, set())
    if tool not in allowed:
        raise PolicyViolation(f"{agent} is not allowed to use tool '{tool}'")


def is_safe_url(url: str) -> bool:
    """判断 URL 是否可被外部抓取：仅 http/https，且不能指向本地/内网。"""
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if not host:
        return False
    if host in {"localhost"} or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (ip.is_private or ip.is_loopback or ip.is_link_local)


def sanitize_source_url(url: str) -> str:
    """把不安全的 URL 折叠成空串，安全 URL 原样返回。"""
    return url if is_safe_url(url) else ""


def redact_secrets(value: Any) -> Any:
    """递归把含敏感关键字（token/password/...）的 dict key 的值涂黑为 [REDACTED]。"""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_l = str(key).lower()
            if any(part in key_l for part in SECRET_KEY_PARTS):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_secrets(item)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):
        return _SECRET_ASSIGNMENT_RE.sub(r"\1\2[REDACTED]", value)
    return copy.deepcopy(value)
