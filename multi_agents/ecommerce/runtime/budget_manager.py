"""
BudgetManager：LLM / 搜索 / 抓取 / 外部 API 用量与成本预算控制。

【正经注释】
围绕 governance state 的 usage 计数做"是否还能调用某类资源"判断，并提供
超预算降级记录。预算耗尽时由调用方（如 OpportunityScoringAgent）主动把
LLM 分支降级为规则分支，并通过 record_degradation 在 governance 上标记
budget_exceeded / degraded_by_budget，保证审计可见。
estimated_cost_usd 一旦超过 max_estimated_cost_usd 也会触发 budget_exceeded。

【大白话注释】
算账本：每次用大模型 / 搜索 / 抓页面 / 调外部 API，都问一句"还能不能用？"，
超了就不能用。超预算后调用方要自己降级（比如改走规则），降级时调一下
record_degradation 把这件事记进治理日志，后面好统计到底降了几次、是不是
钱花超了。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multi_agents.ecommerce.runtime.telemetry import increment_usage, record_event


USAGE_KEYS = {
    "llm": "llm_call_count",
    "search": "search_call_count",
    "scrape": "scrape_call_count",
    "external_api": "external_api_call_count",
}


@dataclass(frozen=True)
class BudgetConfig:
    """四类资源调用上限 + 累计成本上限（USD）。"""

    max_llm_calls: int = 20
    max_search_calls: int = 80
    max_scrape_calls: int = 20
    max_external_api_calls: int = 20
    max_estimated_cost_usd: float = 1.0


class BudgetManager:
    """基于 governance state 的预算闸门。

    【正经注释】只读 / 自增 governance.usage，不改业务 state。
    【大白话注释】看一眼账本够不够用（can_use），用一次记一次（record），
    钱花超了就把 budget_exceeded 拍上。降级时调 record_degradation。
    """

    def __init__(self, governance: dict[str, Any], config: BudgetConfig | None = None):
        self.governance = governance
        self.config = config or BudgetConfig()

    def _usage_key(self, kind: str) -> str:
        if kind not in USAGE_KEYS:
            raise ValueError(f"unknown budget kind: {kind}")
        return USAGE_KEYS[kind]

    def _limit_for(self, kind: str) -> int:
        return {
            "llm": self.config.max_llm_calls,
            "search": self.config.max_search_calls,
            "scrape": self.config.max_scrape_calls,
            "external_api": self.config.max_external_api_calls,
        }[kind]

    def can_use(self, kind: str) -> bool:
        """当前用量是否仍在预算内。"""
        usage = self.governance.setdefault("usage", {})
        return int(usage.get(self._usage_key(kind), 0)) < self._limit_for(kind)

    def record(self, kind: str, estimated_cost_usd: float = 0.0) -> None:
        """记一次资源消耗；累计成本超上限则置 budget_exceeded。"""
        increment_usage(self.governance, self._usage_key(kind), 1)
        if estimated_cost_usd:
            increment_usage(self.governance, "estimated_cost_usd", estimated_cost_usd)
        usage = self.governance.setdefault("usage", {})
        if float(usage.get("estimated_cost_usd", 0.0)) > self.config.max_estimated_cost_usd:
            self.governance["budget_exceeded"] = True

    def record_degradation(self, agent: str, detail: str) -> None:
        """预算耗尽导致降级时记录事件，并置 budget_exceeded / degraded_by_budget。"""
        self.governance["budget_exceeded"] = True
        self.governance["degraded_by_budget"] = True
        record_event(
            self.governance,
            kind="budget",
            agent=agent,
            detail=detail,
            degraded_by_budget=True,
        )
