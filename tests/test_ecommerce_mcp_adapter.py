import pytest

from multi_agents.ecommerce.runtime.telemetry import empty_governance_state, summarize_governance
from multi_agents.ecommerce.tools.mcp_adapter import (
    make_mcp_augmented_search_fn,
    normalize_mcp_result,
)


def test_normalize_mcp_result_maps_to_ecommerce_source_shape():
    raw = {
        "title": "MCP result",
        "url": "https://example.com/mcp",
        "content": "battery leakage complaints",
        "tool_name": "search",
        "server_name": "demo",
    }

    source = normalize_mcp_result(raw)

    assert source["title"] == "MCP result"
    assert source["href"] == "https://example.com/mcp"
    assert source["body"] == "battery leakage complaints"
    assert source["source_type"] == "mcp"
    assert source["tool_name"] == "search"
    assert source["server_name"] == "demo"


@pytest.mark.asyncio
async def test_mcp_augmented_search_combines_base_and_mcp_results():
    governance = empty_governance_state()
    mcp_context = {"enabled": True, "strategy": "fast", "tool_calls": []}

    async def base_search(query, max_results):
        return [{"title": "Base", "href": "https://example.com/base", "body": "base"}]

    async def mcp_search(query, max_results, mcp_configs, mcp_strategy):
        return [{"title": "MCP", "url": "https://example.com/mcp", "content": "mcp"}]

    search = make_mcp_augmented_search_fn(
        base_search,
        mcp_enabled=True,
        mcp_configs=[{"name": "demo"}],
        mcp_strategy="fast",
        governance=governance,
        mcp_context=mcp_context,
        mcp_search_fn=mcp_search,
    )

    results = await search("portable blender", 5)

    assert [row["title"] for row in results] == ["Base", "MCP"]
    assert summarize_governance(governance)["external_api_call_count"] == 1
    assert mcp_context["tool_calls"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_mcp_failure_returns_base_results_and_records_failure():
    governance = empty_governance_state()
    mcp_context = {"enabled": True, "strategy": "fast", "tool_calls": []}

    async def base_search(query, max_results):
        return [{"title": "Base", "href": "https://example.com/base", "body": "base"}]

    async def mcp_search(query, max_results, mcp_configs, mcp_strategy):
        raise RuntimeError("mcp down")

    search = make_mcp_augmented_search_fn(
        base_search,
        mcp_enabled=True,
        mcp_configs=[{"name": "demo"}],
        mcp_strategy="fast",
        governance=governance,
        mcp_context=mcp_context,
        mcp_search_fn=mcp_search,
    )

    results = await search("portable blender", 5)

    assert results == [{"title": "Base", "href": "https://example.com/base", "body": "base"}]
    assert summarize_governance(governance)["failure_count"] == 1
    assert mcp_context["tool_calls"][0]["status"] == "failed"
