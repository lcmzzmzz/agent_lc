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

from multi_agents.ecommerce.runtime.policy_guard import redact_secrets
from multi_agents.ecommerce.runtime.telemetry import record_event

T = TypeVar("T")


class ExecutionGuard:
    """节点执行护栏：把异步 operation 包起来，提供超时 + 重试 + 兜底，所有结果写入 governance 事件流。

    【正经注释】
    治理四件套之一。围绕 governance state 的执行护栏，run() 是核心入口，按「有限状态机」
    管理一次执行：循环尝试（最多 max_retries+1 次）→ 一次成功 / 重试后成功 / 走兜底 / 彻底失败
    四种出口。除「一次成功」外，每个出口都通过 record_event 写进 governance，保证重试/兜底/失败
    在审计与 evaluation summary 里可统计。超时（asyncio.TimeoutError）和业务异常在 except 里被
    统一处理。依赖 policy_guard.redact_secrets 给异常信息脱敏，防止密钥落进审计。

    【大白话注释】
    给每个节点的执行套一层「保镖」：
    - 卡死了（超时）就掐掉、能重试就重来；
    - 连着重试都不行、但给了兜底方案，就走兜底（Plan B）；
    - 兜底也没给，就老实记一笔「失败」并把错误抛上去。
    不管走哪条路，都往治理账本记一笔，方便统计到底重试了几次、兜底了几次、彻底失败几次。
    报错信息写进账本前先打码（涂掉密钥），不会把 token 之类的东西泄露进审计文件。

    一句话总结：节点执行的「超时 / 重试 / 兜底」三件套 + 全程审计。
    """

    def __init__(self, governance: dict[str, Any]):
        """持 governance 引用（与其他三件套共享同一本账本）。

        【正经注释】构造器注入 governance（同 BudgetManager），self.governance 持引用，
        run() 里所有 record_event 都写这本账本。

        【大白话注释】记住要往哪本治理账本上记事——这本账本和别家（BudgetManager/各 agent）是同一本。
        """
        self.governance = governance

    def _safe_error_message(self, exc: Exception | None) -> str:
        """把异常信息脱敏后返回（防止密钥落进 governance 审计）。

        【正经注释】exc 为 None 返回空串；否则用 redact_secrets 包一层 {"error": str(exc)}，
        利用其 str 分支的正则把串里写死的 key=value 敏感赋值涂黑，再取回脱敏后的 error 串。

        【大白话注释】给报错信息「打码」：异常里要是夹着 token=xxx、api_key=yyy 这种，
        涂成 [REDACTED] 再交出去，免得密钥被写进审计文件泄露。没异常就返回空串。

        Args:
            exc: 捕获到的异常，可为 None（大白话：报的错，没有就传 None）

        Returns:
            str: 脱敏后的错误信息（大白话：打完码、能安全写进账本的报错文案）
        """
        if exc is None:
            return ""  # 没异常 → 空串
        # 正经注释：包成 {"error": ...} 走脱敏——key="error" 不含敏感词，但 value 串里写死的 "token=xxx" 会被正则涂黑
        # 大白话：把报错串塞进脱敏函数，里面的密钥会被打码
        redacted = redact_secrets({"error": str(exc)})
        return str(redacted.get("error", ""))  # 取回打码后的文案

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
        """执行 operation，按超时/重试/兜底策略返回结果，全程记 governance。

        【正经注释】
        run() 是有限状态机，四种出口（除「一次成功」外，每个出口都记 governance）：
          ① 一次成功（retry_count=0）：直接返回，不记事件；
          ② 重试后成功（retry_count>0）：记 kind="retry" 事件后返回；
          ③ 全部失败但传了 fallback：执行 fallback，记 kind="fallback"（fallback_used=True）后返回其结果；
          ④ 全部失败且无 fallback：记 kind="failure"（带 error_type/error_message）后 raise 最后一次异常。
        超时（asyncio.wait_for 超时抛 TimeoutError）和业务异常统一进 except，进入重试/兜底/失败逻辑。
        异常信息写账本前一律过 _safe_error_message 脱敏。

        【大白话注释】
        「跑一件事，能成就成，不成就想办法兜住，兜不住就报错」——具体规则：
        - 第一次就成：直接把结果还给你，啥也不记；
        - 第一次没成、但重试之后成了：记一笔「重试后成功」，把结果还给你；
        - 怎么试都不成，但你给了兜底方案：跑兜底方案，记一笔「走了 Plan B」，把兜底结果还给你；
        - 怎么试都不成、也没兜底：记一笔「彻底失败」，把最后一次报的错抛出去（让上层处理）。
        事情卡太久（超过 timeout_ms）也算失败，和报错一样处理。报错写进账本前先打码。

        Args:
            name: 节点/agent 名（大白话：谁在执行，用于审计）
            operation: 无参异步可调用，真正干的事（大白话：要跑的那件事）
            timeout_ms: 单次尝试超时毫秒数（大白话：卡多久算超时）
            max_retries: 最大重试次数，默认 0=不重试（大白话：失败后最多再试几次）
            fallback: 兜底协程，None=无兜底（大白话：Plan B，没有就传 None）
            fallback_reason: 走兜底时记的说明，空则用脱敏后的错误（大白话：为啥走 Plan B 的一句话）

        Returns:
            T: operation（或 fallback）的执行结果（大白话：要的那件事的结果）
        """
        retry_count = 0  # 正经注释：累计重试次数，用于审计。大白话：重试计数器
        last_exc: Exception | None = None  # 正经注释：记录最后一次异常，兜底/失败时用。大白话：记住最后一次报的什么错
        # ── 循环尝试：range(max_retries+1) 保证至少跑一次，最多跑 max_retries+1 次 ──
        for attempt in range(max_retries + 1):
            try:
                # 正经注释：wait_for 给 operation 套超时；超时抛 asyncio.TimeoutError（Exception 子类，会被下面 except 接住）
                # 大白话：跑这件事，但卡到 timeout 就掐掉（算超时失败）
                result = await asyncio.wait_for(operation(), timeout=timeout_ms / 1000)
                # ★ 出口①/②：本次成功。retry_count>0 表示之前失败过 → 出口②（记 retry）；=0 → 出口①（静默返回）
                if retry_count:
                    record_event(
                        self.governance,
                        kind="retry",
                        agent=name,
                        detail="operation succeeded after retry",
                        retry_count=retry_count,
                    )
                return result  # 返回结果（出口①或②的终点）
            except Exception as exc:
                # 正经注释：超时(TimeoutError)和业务异常都进这里。记下异常，判断是否还有重试机会。
                last_exc = exc
                if attempt < max_retries:  # 还有重试机会 → 计数 +1，continue 进入下一次尝试
                    retry_count += 1
                    continue
                # 没有重试机会了（attempt == max_retries）→ 跳出循环，进入下面的兜底/失败分支

        # ── 所有尝试都失败后的两条出路 ──
        if fallback is not None:
            # ★ 出口③：有兜底 → 执行 fallback，记 fallback 事件，返回兜底结果（不抛异常）
            result = await fallback()
            safe_error = self._safe_error_message(last_exc)  # 脱敏最后一次异常，写进审计
            record_event(
                self.governance,
                kind="fallback",
                agent=name,
                detail=fallback_reason or safe_error,  # 优先用调用方给的 reason，否则用脱敏错误
                retry_count=retry_count,
                fallback_used=True,  # 标记：走了兜底（summarize 据此统计 fallback_count）
                error_type=type(last_exc).__name__ if last_exc else "",  # 异常类名（如 TimeoutError）
                error_message=safe_error,
            )
            return result

        # ★ 出口④：无兜底且全失败 → 记 failure 事件，抛出最后一次异常（硬失败，交上层处理）
        safe_error = self._safe_error_message(last_exc)
        record_event(
            self.governance,
            kind="failure",
            agent=name,
            detail=safe_error,
            retry_count=retry_count,
            error_type=type(last_exc).__name__ if last_exc else "",
            error_message=safe_error,
        )
        if last_exc is not None:
            raise last_exc  # 原样抛回上层（如 graph._research_node 的 except 接住后转 partial）
        raise RuntimeError(f"{name} failed without exception")  # 防御性兜底：理论上进不来（没异常不会走到这）
