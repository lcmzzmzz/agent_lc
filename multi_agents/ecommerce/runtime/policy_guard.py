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

import copy                  # redact_secrets 兜底：对不可识别的值（int/bool/对象）深拷贝原样返回
import ipaddress             # 标准库 IP 解析：判断 host 是不是私网/环回/链路本地地址
import re                    # 正则：用于把串里形如 "token=xxx" 的敏感赋值涂黑
from typing import Any       # Any 类型标注（redact_secrets 的输入类型是任意）
from urllib.parse import urlparse  # URL 解析：把 url 拆成 scheme/host/port/...


# ── 三张白名单：校验入口参数用的「合法取值集合」──
ALLOWED_DEPTHS = {"fast", "standard", "deep"}                          # 允许的研究深度三档（控制检索量/并发量）
ALLOWED_MARKETS = {"US", "UK", "DE", "JP"}                             # 允许的目标市场（渠道/价格区间口径）
ALLOWED_PLATFORMS = {"amazon", "google", "reddit", "tiktok", "youtube", "web"}  # 允许的关注平台

# dict 的 key 里只要命中这些片段之一，对应 value 就涂黑为 [REDACTED]（如 authorization / api_token）
SECRET_KEY_PARTS = ("token", "api_key", "apikey", "authorization", "password", "secret")

# 【正经注释】匹配「键名 = 值 / 键名 : 值」形式的敏感赋值串，捕获三组后把【值】替换成 [REDACTED]。
#   组1 = 含敏感词的键名（[a-z0-9_]* 包夹一个敏感词），(?i) 大小写不敏感，\b 词边界防止误命中普通词。
#   组2 = 分隔符 = 或 :（前后可有空白）。
#   组3 = 值（连续非 空白/逗号/分号 字符），正则只替换这一组。
# 【大白话注释】专抓串里写死的密钥，比如 "TAVILY_API_KEY=tvly-xxxx" → "TAVILY_API_KEY=[REDACTED]"。
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([a-z0-9_]*(?:token|api_key|apikey|authorization|password|secret)[a-z0-9_]*)"  # 组1：含敏感词的键名
    r"\s*([=:])\s*"                                                                          # 组2：分隔符 = 或 :
    r"([^\s,;]+)"                                                                            # 组3：值（到空白/逗号/分号为止）
)

# 【正经注释】各 Agent 的工具白名单：assert_tool_allowed 据此拦截越权调用。
# 例如 TrendResearchAgent 只能 "search"，想调 "llm" 就会被拦下 → 抛 PolicyViolation。
# 【大白话注释】给每个角色配一张「能用的工具卡」，没卡的工具不让碰。
TOOL_PERMISSIONS = {
    "TrendResearchAgent": {"search"},                          # 趋势：只能检索
    "CompetitorAnalysisAgent": {"search"},                     # 竞品：只能检索
    "ReviewInsightAgent": {"review_scrape", "search"},         # 评论：可抓评论 + 检索（多一项 review_scrape，因要调 Apify 抓评论）
    "OpportunityScoringAgent": {"llm", "rule_score"},          # 评分：可调 LLM / 走规则评分
    "EcommerceReportWriterAgent": {"state_read", "markdown_write"},  # 写报告：只读 state + 拼 Markdown
    "QualityReviewerAgent": {"state_read", "quality_check"},         # 质检：只读 state + 质检
}


class PolicyViolation(ValueError):
    """请求 / 工具调用违反运行时策略时抛出。"""  # 继承 ValueError：业务校验失败归为一类，调用方 catch ValueError 即可


def validate_research_request(
    *,
    query: str,                # 选品关键词
    target_market: str,        # 目标市场
    platforms: list[str] | None,  # 关注平台（None 视为合法，不校验）
    depth: str,                # 研究深度
) -> None:
    """校验单次研究请求的基础约束；不通过抛 PolicyViolation。"""
    cleaned_query = (query or "").strip()       # query 为 None → ""，再去首尾空白
    if not cleaned_query:                       # 空 query → 拒（防止无意义研究跑一整轮）
        raise PolicyViolation("query must not be empty")
    if len(cleaned_query) > 200:                # 超长 query → 拒（防止把一大段 prompt 当关键词塞进来）
        raise PolicyViolation("query must be 200 characters or fewer")
    if depth not in ALLOWED_DEPTHS:             # depth 不在白名单 → 拒（防 depth="xxx" 触发未知分支）
        raise PolicyViolation(f"depth must be one of {sorted(ALLOWED_DEPTHS)}")
    if target_market not in ALLOWED_MARKETS:    # market 不在白名单 → 拒（market 影响检索/价格口径，必须可控）
        raise PolicyViolation(f"target_market must be one of {sorted(ALLOWED_MARKETS)}")
    invalid_platforms = [p for p in (platforms or []) if p not in ALLOWED_PLATFORMS]  # 找出非法平台
    if invalid_platforms:                       # 有任何非法平台 → 拒（platforms or [] 让 None 也能过这关）
        raise PolicyViolation(f"unsupported platforms: {invalid_platforms}")


def assert_tool_allowed(agent: str, tool: str) -> None:
    """检查某个 Agent 是否有权使用某个工具；越权抛 PolicyViolation。"""
    allowed = TOOL_PERMISSIONS.get(agent, set())  # 取该 agent 的白名单；没登记的 agent → 空集合（任何工具都不让用）
    if tool not in allowed:                       # 工具不在白名单 → 越权
        raise PolicyViolation(f"{agent} is not allowed to use tool '{tool}'")


def is_safe_url(url: str) -> bool:
    """判断 URL 是否可被外部抓取：仅 http/https，且不能指向本地/内网。"""
    parsed = urlparse(url or "")                  # url 为 None → "" 再解析；parsed 是带 scheme/host/... 的命名元组
    if parsed.scheme not in {"http", "https"}:    # 非 http(s)（如 file://、ftp://、javascript:）→ 不安全
        return False
    host = parsed.hostname                        # 取 host（已自动转小写、去端口）
    if not host:                                  # 没 host（如 "http://"）→ 不安全
        return False
    if host in {"localhost"} or host.endswith(".local"):  # 文本形式的本地域名 → 不安全
        return False
    try:
        ip = ipaddress.ip_address(host)           # 尝试把 host 当 IP 解析（如 "192.168.1.1"）
    except ValueError:                            # 解析失败 → host 是普通域名（如 example.com）→ 安全
        return True
    # 是 IP：私网(10./172.16./192.168.) / 环回(127.) / 链路本地(169.254.) 全部拒，防 SSRF 打内网
    return not (ip.is_private or ip.is_loopback or ip.is_link_local)


def sanitize_source_url(url: str) -> str:
    """把不安全的 URL 折叠成空串，安全 URL 原样返回。"""
    return url if is_safe_url(url) else ""        # 一行三目：不安全 → ""（下游当无此来源处理），安全 → 原样


def redact_secrets(value: Any) -> Any:
    """递归把含敏感关键字（token/password/...）的 dict key 的值涂黑为 [REDACTED]。"""
    if isinstance(value, dict):                       # dict：逐个 key 检查
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_l = str(key).lower()                  # key 转小写做匹配（大小写不敏感）
            if any(part in key_l for part in SECRET_KEY_PARTS):  # key 命中任一敏感片段 → 值整体涂黑
                redacted[key] = "[REDACTED]"
            else:                                     # 普通字段 → 递归进去（值本身可能是嵌套 dict/list/串）
                redacted[key] = redact_secrets(item)
        return redacted
    if isinstance(value, list):                       # list：逐项递归
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):                      # tuple：逐项递归后重新包成 tuple（保持类型）
        return tuple(redact_secrets(item) for item in value)
    if isinstance(value, str):                        # str：抓串里写死的 "key=value" 敏感赋值 → 把值涂黑
        return _SECRET_ASSIGNMENT_RE.sub(r"\1\2[REDACTED]", value)  # \1=键名 \2=分隔符，值换成 [REDACTED]
    return copy.deepcopy(value)                       # 其他（int/bool/None/对象...）：深拷贝原样返回
