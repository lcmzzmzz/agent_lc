"""
治理遥测层：治理事件记录 + 用量计数 + 汇总统计。

【正经注释】
治理四件套的「地基」：定义 governance state 的结构与事件 schema，
提供三个原子操作——record_event（写一条治理事件）、increment_usage（用量计数）、
summarize_governance（把账本浓缩成可比较的指标）。BudgetManager / ExecutionGuard 都通过
record_event / increment_usage 写账本，evaluation.py 通过 summarize_governance 把账本
落进 evaluation.json。所有写操作都「原地修改」传入的 governance dict（共享引用设计），
不返回新账本。

【大白话注释】
这就是治理层的「账本和记账笔」：
- GovernanceEvent：规定「一条治理记录」长什么样（谁、干了啥、什么时间、有没有被拦/降级）；
- record_event：往账本上写一条记录（最常用，整个治理层调用最频繁）；
- increment_usage：用量数字 +1（搜索了几次、调了几次大模型、花了多少钱）；
- summarize_governance：把整本账算成几个关键数（失败几次、降级几次、花了多少钱），交出去写报告。
注意这些函数都是直接在传进来的账本上涂改，不另建新账本——因为全系统共用同一本。

一句话总结：治理层的「记账工具」，所有治理动作最终都通过这里落进账本、再被统计成指标。
"""

from __future__ import annotations

import time
from typing import Any, TypedDict


class GovernanceEvent(TypedDict, total=False):
    """一条治理事件的 schema（所有字段可选，total=False）。

    【正经注释】
    TypedDict 描述 governance.events 列表里每条记录的字段。total=False 表示所有字段
    可选——record_event 只填用到的字段（如 policy 事件不带 error_type/error_message）。
    kind 是事件类型，其余字段从不同维度描述这次事件。

    【大白话注释】
    一条「记账记录」的模板：记的是「谁（agent）、什么类型（kind）、什么细节（detail）、
    什么时间（timestamp_ms 自动盖）、重试了几次、有没有走兜底/被预算降级/被策略拦、报错信息」。
    用不到的字段就不填。
    """

    kind: str  # 正经注释：事件类型（policy/budget/retry/fallback/failure）。大白话：这条记录属于哪一类
    agent: str  # 正经注释：触发主体（agent 名或节点名）。大白话：谁干的
    detail: str  # 正经注释：人可读的细节描述。大白话：一句话说清发生了啥
    timestamp_ms: int  # 正经注释：毫秒级时间戳（record_event 自动盖）。大白话：什么时候记的，自动填
    retry_count: int  # 正经注释：重试次数（成功后记 retry 事件时才非 0）。大白话：失败后重来几次才成
    fallback_used: bool  # 正经注释：是否走了兜底分支。大白话：是不是用了 Plan B
    degraded_by_budget: bool  # 正经注释：是否因预算耗尽而降级。大白话：是不是因为「没钱了」才降级
    policy_blocked: bool  # 正经注释：是否被策略拦截。大白话：是不是因为「没权限」被拦
    error_type: str  # 正经注释：异常类名（fallback/failure 用，已脱敏）。大白话：报的什么类型的错
    error_message: str  # 正经注释：异常信息（已脱敏，密钥被涂黑）。大白话：报错的具体内容


def empty_governance_state() -> dict[str, Any]:
    """构造一个全新的空治理账本（governance state 的标准初始结构）。

    【正经注释】
    governance dict 的标准结构：events（事件流）、usage（三类资源用量 + 累计成本）、
    budget_exceeded / degraded_by_budget（两个预算标志位）。create_initial_state 用它
    初始化 state["governance"]，之后全程共享这一个 dict 的引用（四件套都改同一本）。

    【大白话注释】
    开一本崭新的「治理账本」，里面分三块——
    - events：记事本（一条条事件往后追加）；
    - usage：计数器（大模型/搜索/外部 API 各调了几次、估算花了多少美金）；
    - 两个标志位：「预算超了吗」「有没有因为预算降过级」。
    一开始全是空的/False，跑的过程中边跑边往里写。

    Returns:
        dict[str, Any]: 空 governance 账本（大白话：一本崭新的、还没记任何东西的治理账本）
    """
    return {
        "events": [],  # 正经注释：治理事件流，record_event 往这里 append。大白话：记事本，一条条往里加
        "usage": {  # 正经注释：资源用量计数。大白话：各类调用的计数器
            "llm_call_count": 0,  # 大模型调用次数
            "search_call_count": 0,  # 搜索调用次数
            "external_api_call_count": 0,  # 外部 API（如 Apify）调用次数
            "estimated_cost_usd": 0.0,  # 估算累计成本（美元）
        },
        "budget_exceeded": False,  # 正经注释：预算是否已超（record_degradation 或成本超上限时置 True）。大白话：钱花超了吗
        "degraded_by_budget": False,  # 正经注释：是否因预算降过级。大白话：有没有因为没钱而降级过
    }


def record_event(
    governance: dict[str, Any],
    *,
    kind: str,
    agent: str,
    detail: str,
    retry_count: int = 0,
    fallback_used: bool = False,
    degraded_by_budget: bool = False,
    policy_blocked: bool = False,
    error_type: str = "",
    error_message: str = "",
) -> GovernanceEvent:
    """往 governance 账本写一条治理事件（原地修改 + 返回该事件）。

    【正经注释】
    治理层被调用最频繁的函数。两步：① 构造带 timestamp_ms 的事件 dict；
    ② governance.setdefault("events", []).append(event) 原地追加进事件流。
    若 degraded_by_budget=True，额外置 budget_exceeded / degraded_by_budget 两个标志位
    （策略拦截 policy_blocked=True 不会进这个分支，不碰预算标志——这是两种「记一笔」的关键区别）。
    副作用（改 governance）才是主角，返回值只是顺手把这条事件交给调用方。

    【大白话注释】
    就是「往账本上记一条」：把这条记录的时间戳补上，塞进账本的记事本里。
    如果是因为「预算超了」才记的，顺手把「钱花超了」「降过级」两个标签也贴上；
    如果只是「策略拦截」（没权限），只记一条、不碰这两个标签。
    它是直接在传进来的账本上涂改（不建新账本），改完把这条记录也返回给调用方。

    Args:
        governance: 要写入的治理账本（大白话：要往哪本账上记）
        kind: 事件类型 policy/budget/retry/fallback/failure（大白话：这属于哪一类）
        agent: 触发主体（大白话：谁干的）
        detail: 人可读细节（大白话：一句话说清楚发生了啥）
        retry_count: 重试次数（大白话：重来了几次）
        fallback_used: 是否走了兜底（大白话：是不是用了 Plan B）
        degraded_by_budget: 是否因预算降级（大白话：是不是没钱了才降级）——会触发置标志位
        policy_blocked: 是否被策略拦截（大白话：是不是没权限被拦）——不置预算标志位
        error_type: 异常类名（大白话：报错类型）
        error_message: 异常信息（大白话：报错内容，需已脱敏）

    Returns:
        GovernanceEvent: 刚写入的那条事件（大白话：刚记下的那条记录，方便调用方继续用）
    """
    event: GovernanceEvent = {
        "kind": kind,
        "agent": agent,
        "detail": detail,
        "timestamp_ms": int(time.time() * 1000),  # 正经注释：自动盖毫秒时间戳。大白话：自动补上「什么时间记的」
        "retry_count": retry_count,
        "fallback_used": fallback_used,
        "degraded_by_budget": degraded_by_budget,
        "policy_blocked": policy_blocked,
    }
    # 正经注释：可选字段——有值才写进事件（避免空串污染）
    # 大白话：报错信息这俩字段，没出错就不填
    if error_type:
        event["error_type"] = error_type
    if error_message:
        event["error_message"] = error_message
    # ★ 正经注释：副作用核心——setdefault 保证拿到 governance 内部的 list（不存在就先建 []），append 真改到账本上
    # ★ 大白话：把这条记录塞进账本的记事本。用 setdefault 是为了保证改的是账本里的那个记事本，而不是另起一本
    governance.setdefault("events", []).append(event)
    # 正经注释：仅预算降级才置这两个标志位；策略拦截（policy_blocked）走不进这里 → 不碰预算标志
    # 大白话：只有「没钱降级」才贴「钱超了」「降过级」俩标签；「没权限被拦」不贴这俩
    if degraded_by_budget:
        governance["budget_exceeded"] = True
        governance["degraded_by_budget"] = True
    return event  # 正经注释：返回值只是顺手交出这条事件；真正生效的是上面的原地修改。大白话：把刚记的这条也递给调用方看一眼


def increment_usage(
    governance: dict[str, Any],
    key: str,
    amount: int | float = 1,
) -> None:
    """给 governance.usage 的某个计数器 +amount（原地修改）。

    【正经注释】
    资源用量计数的原子操作。setdefault 拿 usage dict 引用，再 usage[key] = get(key,0)+amount。
    被 BudgetManager.record 调用（计数 +1 或累加成本 estimated_cost_usd）。

    【大白话注释】
    就是「账本上的某个计数器 +1（或 +金额）」：搜索了一次就把 search_call_count +1，
    花了点钱就把 estimated_cost_usd 加上去。

    Args:
        governance: 治理账本（大白话：哪本账）
        key: usage 里的计数键（大白话：加到哪个计数器上）
        amount: 增量，默认 1（大白话：加多少，数次数就加 1，算钱就加金额）
    """
    usage = governance.setdefault("usage", {})  # 正经注释：拿 usage dict 引用（不存在先建空 dict）。大白话：翻到账本的计数器那页
    usage[key] = usage.get(key, 0) + amount  # 正经注释：原值（无则 0）+ amount。大白话：原来的数 + 这次加的


def summarize_governance(governance: dict[str, Any] | None) -> dict[str, Any]:
    """把 governance 账本浓缩成一组可比较的指标（只读，不改账本）。

    【正经注释】
    治理账本对外的出口：扫 events 按 kind/标志位计数（failure/retry/fallback/policy_block），
    读 usage 的原始计数 + 两个预算标志。evaluation.py:44 调它，结果 merge 进 evaluation.json。
    governance 为 None 时用空账本兜底，保证调用方不报错。

    【大白话注释】
    把整本账「算成几个关键数」：失败几次、重试几次、兜底几次、被策略拦几次、
    大模型/搜索/外部 API 各调了几次、估算花了多少钱、有没有超预算/降过级。
    evaluation.json 里的治理那部分就是它算出来的。它只读不改账本。
    传 None 也不怕，自动当一本空账算。

    Args:
        governance: 治理账本，可为 None（大白话：哪本账，没有就当空账）

    Returns:
        dict[str, Any]: 10 个汇总指标（大白话：浓缩出来的几个关键数字）
    """
    governance = governance or empty_governance_state()  # 正经注释：None 兜底成空账本。大白话：没传账本就当一本空账
    events = governance.get("events", [])  # 正经注释：事件流（空账本 → []）。大白话：翻到记事本
    usage = governance.get("usage", {})  # 正经注释：用量计数。大白话：翻到计数器那页
    return {
        # 正经注释：按 kind/标志位过滤统计（generator + sum）
        # 大白话：数一数各类情况各发生了几次
        "failure_count": sum(1 for e in events if e.get("kind") == "failure"),  # 失败次数
        "retry_count": sum(int(e.get("retry_count", 0)) for e in events),  # 累计重试次数
        "fallback_count": sum(1 for e in events if e.get("fallback_used")),  # 兜底次数
        "policy_block_count": sum(1 for e in events if e.get("policy_blocked")),  # 策略拦截次数
        "budget_exceeded": bool(governance.get("budget_exceeded", False)),  # 是否超预算
        "degraded_by_budget": bool(governance.get("degraded_by_budget", False)),  # 是否因预算降级
        # 正经注释：usage 原始计数（int/float 兜底转换）
        # 大白话：直接读计数器上的数
        "llm_call_count": int(usage.get("llm_call_count", 0)),
        "search_call_count": int(usage.get("search_call_count", 0)),
        "external_api_call_count": int(usage.get("external_api_call_count", 0)),
        "estimated_cost_usd": round(float(usage.get("estimated_cost_usd", 0.0)), 6),  # 正经注释：round 6 位防浮点长尾。大白话：钱保留 6 位小数
    }
