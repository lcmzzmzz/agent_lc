"""
ExecutionGuard：节点执行的统一超时 / 重试 / 兜底包装。

【正经注释】
围绕 governance state 的执行护栏：把一个异步 operation 包起来，提供
- timeout_ms：单次尝试最长执行时间，超时算作失败
- max_retries：失败重试次数（最终成功则记 retry 事件；不重试则 0）
- fallback：所有重试都失败后兜底执行的协程；命中兜底记 fallback 事件
- 无 fallback 且全部失败：记 failure 事件并抛出最后一次异常

所有分支都通过 record_event 写入 governance，保证重试 / 兜底 / 失败在
审计与 evaluation summary 里可统计、可观测。

【大白话注释】
给每个节点的执行套一层"保镖"：卡死了掐掉重来、连着几次都不行就用兜底方案、
实在兜底也没给就老实报失败。不管走哪条路都记一笔进治理日志，方便统计
到底重试了几次、兜底了几次、彻底失败几次。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from multi_agents.ecommerce.runtime.telemetry import record_event

T = TypeVar("T")


class ExecutionGuard:
    """节点执行护栏：超时 + 重试 + 兜底，所有结果都写入 governance 事件流。"""

    def __init__(self, governance: dict[str, Any]):
        self.governance = governance

    async def run(
        self,
        *,
        name: str,
        operation: Callable[[], Awaitable[T]],
        timeout_ms: int,
        max_retries: int = 0,
        fallback: Callable[[], Awaitable[T]] | None = None,
        fallback_reason: str = "",
    ) -> T:
        retry_count = 0
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(operation(), timeout=timeout_ms / 1000)
                if retry_count:
                    record_event(
                        self.governance,
                        kind="retry",
                        agent=name,
                        detail="operation succeeded after retry",
                        retry_count=retry_count,
                    )
                return result
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    retry_count += 1
                    continue

        if fallback is not None:
            result = await fallback()
            record_event(
                self.governance,
                kind="fallback",
                agent=name,
                detail=fallback_reason or str(last_exc),
                retry_count=retry_count,
                fallback_used=True,
                error_type=type(last_exc).__name__ if last_exc else "",
                error_message=str(last_exc) if last_exc else "",
            )
            return result

        record_event(
            self.governance,
            kind="failure",
            agent=name,
            detail=str(last_exc),
            retry_count=retry_count,
            error_type=type(last_exc).__name__ if last_exc else "",
            error_message=str(last_exc) if last_exc else "",
        )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"{name} failed without exception")
