"""
EcomResearcher 深度档位配置。

【正经注释】
将 fast / standard / deep 三档调研深度映射为可量化的执行参数，
控制每个 Agent 的最大 query 数、最大数据源数以及是否启用质量复查与 query 扩展。
未知深度回退到 standard。

【大白话注释】
给"快速 / 标准 / 深度"三档调研究深浅：
快速少搜一点、深度多搜一点。配置表集中管理，免得散在各处。
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from multi_agents.ecommerce.runtime.budget_manager import BudgetConfig

DEPTH_CONFIGS: dict[str, dict[str, Any]] = {
    "fast": {
        "max_sources_per_agent": 3,
        "max_queries_per_agent": 2,
        "enable_quality_review": True,
        "enable_query_expansion": False,
    },
    "standard": {
        "max_sources_per_agent": 6,
        "max_queries_per_agent": 4,
        "enable_quality_review": True,
        "enable_query_expansion": True,
    },
    "deep": {
        "max_sources_per_agent": 10,
        "max_queries_per_agent": 6,
        "enable_quality_review": True,
        "enable_query_expansion": True,
    },
}


def get_depth_config(depth: str) -> dict[str, Any]:
    """按档位名称取配置；未知档位回退到 standard。

    【正经注释】返回 deepcopy，避免调用方就地修改污染全局配置。
    【大白话注释】要哪一档就给哪一档；名字写错了就按标准档来。
    """
    return deepcopy(DEPTH_CONFIGS.get(depth, DEPTH_CONFIGS["standard"]))


def get_budget_config() -> BudgetConfig:
    """从环境变量读取预算配置；未设置则用 BudgetConfig 默认值。

    【正经注释】所有键都给默认值，缺省即等价于 BudgetConfig()。
    支持的环境变量：ECOMMERCE_MAX_LLM_CALLS / ECOMMERCE_MAX_SEARCH_CALLS /
    ECOMMERCE_MAX_SCRAPE_CALLS / ECOMMERCE_MAX_EXTERNAL_API_CALLS /
    ECOMMERCE_MAX_ESTIMATED_COST_USD。
    【大白话注释】预算能从环境变量调；不设就用默认值。
    """
    return BudgetConfig(
        max_llm_calls=int(os.environ.get("ECOMMERCE_MAX_LLM_CALLS", "20")),
        max_search_calls=int(os.environ.get("ECOMMERCE_MAX_SEARCH_CALLS", "80")),
        max_scrape_calls=int(os.environ.get("ECOMMERCE_MAX_SCRAPE_CALLS", "20")),
        max_external_api_calls=int(os.environ.get("ECOMMERCE_MAX_EXTERNAL_API_CALLS", "20")),
        max_estimated_cost_usd=float(os.environ.get("ECOMMERCE_MAX_ESTIMATED_COST_USD", "1.0")),
    )
