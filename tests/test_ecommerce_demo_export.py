"""Tests for ecommerce demo case export manifest helpers."""

from scripts.export_ecommerce_demo_cases import _build_error_entry, _build_success_entry


def test_build_error_entry_does_not_emit_missing_artifact_links():
    case = {
        "slug": "portable-blender",
        "title": "Portable Blender",
        "query": "portable blender",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "standard",
    }

    entry = _build_error_entry(case, "RuntimeError: search unavailable")

    assert entry["status"] == "error"
    assert entry["error"] == "RuntimeError: search unavailable"
    assert entry["slug"] == "portable-blender"
    assert "report" not in entry
    assert "evaluation" not in entry
    assert "audit" not in entry
    assert "quality" not in entry


def test_manifest_preserves_governance_summary_fields():
    """治理指标（重试 / 策略拦截 / 调用计数 / 成本）必须原样透传进 manifest 条目。

    回归保护：_build_success_entry 整包透传 summary，不做字段白名单，
    所以 summarize_governance() 产出的所有 governance 字段都得保留下来，
    前端评估页才能显示这些 KPI。
    """
    case = {
        "slug": "portable-blender",
        "title": "Portable Blender",
        "query": "portable blender",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "standard",
    }
    summary = {
        "overall_score": 6.5,
        "confidence": 0.7,
        "evidence_count": 3,
        "fallback_count": 1,
        "duration_ms": 1000,
        "quality_passed": True,
        "failure_count": 0,
        "retry_count": 1,
        "policy_block_count": 0,
        "budget_exceeded": False,
        "degraded_by_budget": False,
        "llm_call_count": 2,
        "search_call_count": 6,
        "scrape_call_count": 0,
        "external_api_call_count": 0,
        "estimated_cost_usd": 0.02,
    }

    entry = _build_success_entry(case, summary)

    # 关键治理字段必须原样保留（计划里点名要的几个）
    assert entry["summary"]["retry_count"] == 1
    assert entry["summary"]["policy_block_count"] == 0
    assert entry["summary"]["llm_call_count"] == 2
    assert entry["summary"]["search_call_count"] == 6
    assert entry["summary"]["estimated_cost_usd"] == 0.02
    assert entry["summary"]["budget_exceeded"] is False
    # 原有评估字段也得在（保证不是只留 governance 而丢了评估分）
    assert entry["summary"]["overall_score"] == 6.5
    # 成功条目不该带 error 形状的字段
    assert "status" not in entry
    assert "error" not in entry
    # artifact 链接齐全
    assert entry["report"].endswith("portable-blender/report.md")
    assert entry["evaluation"].endswith("portable-blender/evaluation.json")


def test_success_entry_includes_agentops_artifact_links():
    case = {
        "slug": "portable-blender",
        "title": "Portable Blender",
        "query": "portable blender",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "standard",
    }
    summary = {
        "overall_score": 6.5,
        "trace_node_count": 7,
        "human_overridden_score_count": 1,
        "mcp_tool_call_count": 0,
    }

    entry = _build_success_entry(case, summary)

    assert entry["trace"].endswith("portable-blender/trace.json")
    assert entry["human_review"].endswith("portable-blender/human-review.json")
    assert entry["run"].endswith("portable-blender/run.json")
    assert entry["summary"]["trace_node_count"] == 7
    assert entry["summary"]["human_overridden_score_count"] == 1
