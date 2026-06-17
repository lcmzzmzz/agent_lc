"""
Agent 发现协议模块

【正经注释】
本模块实现了 Agent Discovery Protocol（代理发现协议），用于向外暴露 GPT Researcher 提供的服务列表。
通过 /.well-known/agent-discovery.json 端点，其他系统可以自动发现并接入本服务所提供的
研究、报告管理、对话以及实时 WebSocket 流式传输等能力。

【大白话注释】
这个模块就像一张"名片"，告诉别人："嗨，我能提供这些服务！"
别的系统只要访问一个固定的网址，就能知道咱这个研究助手能干啥——
比如帮你做研究、生成报告、陪你聊天、实时推送进度等等。
"""
from typing import Dict, List, Optional  # 正经注释：导入类型提示用于函数签名标注 / 大白话注释：告诉 Python 这些变量是啥类型


def _to_websocket_origin(origin: str) -> str:
    """
    将 HTTP/HTTPS 协议地址转换为对应的 WebSocket 协议地址。

    【正经注释】
    根据输入的 origin 字符串前缀，将 https:// 替换为 wss://，
    将 http:// 替换为 ws://，其他情况原样返回。
    这是因为 WebSocket 协议需要使用 ws/wss 前缀而非 http/https。

    【大白话注释】
    把普通网址变成 WebSocket 专用网址。
    比如 https://xxx.com 变成 wss://xxx.com，
    http://xxx.com 变成 ws://xxx.com。

    Args:
        origin: 原始的 HTTP/HTTPS 地址字符串
    """
    if origin.startswith("https://"):  # 正经注释：检测是否为 HTTPS 安全连接 / 大白话注释：看看是不是加密的 https 开头
        return "wss://" + origin[len("https://"):]  # 正经注释：替换为安全的 WebSocket 协议前缀 / 大白话注释：把 https 换成 wss
    if origin.startswith("http://"):  # 正经注释：检测是否为普通 HTTP 连接 / 大白话注释：看看是不是普通的 http 开头
        return "ws://" + origin[len("http://"):]  # 正经注释：替换为普通 WebSocket 协议前缀 / 大白话注释：把 http 换成 ws
    return origin  # 正经注释：非 HTTP 协议地址直接返回原值 / 大白话注释：不是 http/https 开头的话就不管了，原样返回


def build_agent_discovery_document(
    origin: str,
    domain: str,
    contact: Optional[str] = None,
) -> Dict[str, object]:
    """
    构建 Agent Discovery 文档，描述本服务所提供的所有 API 能力。

    【正经注释】
    根据 origin 和 domain 信息，生成符合 Agent Discovery Protocol 规范的 JSON 文档。
    文档中包含 research、reports、chat、research_stream 四个服务条目，
    每个条目描述了服务名称、功能、端点地址、通信协议、认证方式等元信息。

    【大白话注释】
    这是组装"名片"内容的函数。把咱能提供的服务一个个列出来：
    - research：帮你做研究
    - reports：管理研究报告
    - chat：跟报告对话问答
    - research_stream：实时推送研究进度
    每个服务都标明了地址、协议、要不要认证等信息。

    Args:
        origin: 服务的基础 URL 地址，如 https://example.com
        domain: 服务所在域名
        contact: 可选的联系方式信息
    """
    normalized_origin = origin.rstrip("/")  # 正经注释：移除末尾的斜杠以确保 URL 格式统一 / 大白话注释：把网址末尾的斜杠去掉，免得拼出来双斜杠
    websocket_origin = _to_websocket_origin(normalized_origin)  # 正经注释：将 HTTP 地址转换为 WebSocket 地址 / 大白话注释：把普通网址变成 ws 网址

    services: List[Dict[str, object]] = [  # 正经注释：定义服务描述列表 / 大白话注释：开始列"名片"上的服务清单
        {
            "name": "research",  # 正经注释：研究服务标识 / 大白话注释：服务的名字——"研究"
            "description": "Submit a research job and generate a report.",  # 正经注释：服务功能描述 / 大白话注释：一句话说明这服务干啥的——提交研究任务并生成报告
            "endpoint": f"{normalized_origin}/report/",  # 正经注释：服务端点 URL / 大白话注释：调用这个服务的网址
            "protocol": "http",  # 正经注释：通信协议类型 / 大白话注释：用的是普通 HTTP 协议
            "auth": "none",  # 正经注释：无需认证 / 大白话注释：不需要登录就能用
            "governance": "none",  # 正经注释：无治理策略 / 大白话注释：没有什么额外限制
            "free_tier": True,  # 正经注释：免费可用 / 大白话注释：免费的，不收钱
        },
        {
            "name": "reports",  # 正经注释：报告管理服务标识 / 大白话注释：服务的名字——"报告管理"
            "description": "Create, list, and manage generated research reports.",  # 正经注释：报告管理功能描述 / 大白话注释：创建、查看和管理研究报告
            "endpoint": f"{normalized_origin}/api/reports",  # 正经注释：报告 API 端点 / 大白话注释：报告管理的接口地址
            "protocol": "http",
            "auth": "none",
            "governance": "none",
            "free_tier": True,
        },
        {
            "name": "chat",  # 正经注释：对话服务标识 / 大白话注释：服务的名字——"对话"
            "description": "Ask follow-up questions against a generated report.",  # 正经注释：对话功能描述 / 大白话注释：对着报告追问问题
            "endpoint": f"{normalized_origin}/api/chat",  # 正经注释：对话 API 端点 / 大白话注释：聊天接口的地址
            "protocol": "http",
            "auth": "none",
            "governance": "none",
            "free_tier": True,
        },
        {
            "name": "research_stream",  # 正经注释：实时流式研究服务标识 / 大白话注释：服务的名字——"实时研究"
            "description": "Realtime WebSocket stream for interactive research runs.",  # 正经注释：WebSocket 实时流描述 / 大白话注释：用 WebSocket 实时推送研究过程
            "endpoint": f"{websocket_origin}/ws",  # 正经注释：WebSocket 端点地址 / 大白话注释：WebSocket 的连接地址
            "protocol": "websocket",  # 正经注释：WebSocket 协议 / 大白话注释：不是普通 http，而是 WebSocket 长连接
            "auth": "none",
            "governance": "none",
            "free_tier": True,
        },
    ]

    document: Dict[str, object] = {  # 正经注释：组装最终的发现文档 / 大白话注释：把"名片"拼装好
        "agent_discovery_version": "0.1",  # 正经注释：协议版本号 / 大白话注释：这个"名片"格式的版本号
        "domain": domain,  # 正经注释：所属域名 / 大白话注释：咱服务的域名
        "services": services,  # 正经注释：服务列表 / 大白话注释：上面列好的所有服务
    }

    if contact:  # 正经注释：如果提供了联系方式则附加到文档中 / 大白话注释：如果有联系人信息就加上
        document["contact"] = contact

    return document  # 正经注释：返回完整的 Agent Discovery 文档 / 大白话注释：把拼好的"名片"交出去
