"""统一 audit 记录写入辅助。

【正经注释】
finalize_audit 把 7 个 agent 各自手写的 state["audit_log"].append({...}) 收敛到一处，
保证 6 个基线字段（agent / status / duration_ms / source_count / confidence / warning）
一致、duration_ms 公式统一，并支持 extra 扩展字段（review 的 review_source 等）。
原地 append（不返回新 list），保 langgraph Annotated[list, operator.add] reducer 语义。

【大白话注释】
7 个 agent 以前各自手写"往审计日志塞一条记录"，字段容易漏抄、计时各算各的。
现在统一交给这个函数填，保证格式一致；review 多出的几个字段用 extra 传进来。
"""

from __future__ import annotations

import time
from typing import Any


def finalize_audit(
    state: dict[str, Any],
    agent: str,
    *,
    status: str,
    source_count: int,
    confidence: float,
    warning: str | None,
    started: float,
    **extra: Any,
) -> None:
    """统一写一条 audit 记录（6 基线字段 + extra 扩展字段）。

    Args:
        state: 研究状态（原地往 state["audit_log"] append 一条）。
        agent: agent 名（与 audit_log / policy / governance 账本一致）。
        status: "success" | "partial"。
        source_count: 证据来源数（int）。
        confidence: 本次置信度（float）。
        warning: 警告文案，无则 None。
        started: 函数开头 time.perf_counter() 的返回值，用于算 duration_ms。
        **extra: 扩展字段（review 传 review_source / search_keyword / review_count /
            platforms / fallback_reason；其余 agent 不传）。

    Note:
        status 与 warning 必须由调用方独立给定——scoring 是 success-but-warning
        语义（恒 success 但 warning 可非空），不能在内部把 warning!=None 映射成 partial。
    """
    state["audit_log"].append({
        "agent": agent,
        "status": status,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "source_count": source_count,
        "confidence": confidence,
        "warning": warning,
        **extra,
    })
