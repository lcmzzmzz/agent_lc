import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.server import ecommerce_api


def _client():
    app = FastAPI()
    app.include_router(ecommerce_api.router)
    return TestClient(app)


def test_ecommerce_research_response_includes_agentops_fields(monkeypatch):
    received_kwargs = {}

    async def fake_run(**kwargs):
        received_kwargs.update(kwargs)
        return {
            "run_id": "ecom_20260622063000_portable-blender_abc123",
            "query": kwargs["query"],
            "target_market": kwargs["target_market"],
            "trend_result": {},
            "competitor_result": {},
            "review_result": {},
            "opportunity_score": {},
            "quality_check": {},
            "audit_log": [],
            "agent_trace": [{"node": "planner"}],
            "evaluation_summary": {"trace_node_count": 1},
            "human_review": {"review_status": "pending"},
            "eval_result": {},
            "mcp_context": {"enabled": False, "strategy": "fast", "tool_calls": []},
            "final_report": "# Report",
            "output_paths": {"trace": "trace.json"},
        }

    monkeypatch.setattr(ecommerce_api, "run_ecommerce_research", fake_run)

    response = _client().post(
        "/api/ecommerce/research",
        json={
            "query": "portable blender",
            "mcp_enabled": True,
            "mcp_strategy": "fast",
            "mcp_configs": [{"name": "demo"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "ecom_20260622063000_portable-blender_abc123"
    assert data["agent_trace"][0]["node"] == "planner"
    assert data["evaluation_summary"]["trace_node_count"] == 1
    assert data["human_review"]["review_status"] == "pending"
    assert received_kwargs["mcp_enabled"] is True
    assert received_kwargs["mcp_strategy"] == "fast"
    assert received_kwargs["mcp_configs"] == [{"name": "demo"}]


def test_human_review_endpoint_saves_payload(monkeypatch, tmp_path):
    run_id = "ecom_20260622063000_portable-blender_abc123"
    saved_payloads = []

    def fake_save(target_run_id, review, output_dir="outputs/ecommerce"):
        saved_payloads.append((target_run_id, review))
        return {"review_status": review["review_status"]}

    monkeypatch.setattr(ecommerce_api, "save_human_review", fake_save)

    response = _client().post(
        f"/api/ecommerce/runs/{run_id}/human-review",
        json={"review_status": "revised", "report_labels": ["citation_weak"]},
    )

    assert response.status_code == 200
    assert response.json()["human_review"]["review_status"] == "revised"
    assert saved_payloads[0][0] == run_id


def test_run_lookup_returns_404_when_missing(monkeypatch):
    """[FIX-4] unknown run id must be 404, not 500."""

    def raise_missing(run_id, output_dir="outputs/ecommerce"):
        raise FileNotFoundError(f"ecommerce run not found: {run_id}")

    monkeypatch.setattr(ecommerce_api, "load_run", raise_missing)

    response = _client().get("/api/ecommerce/runs/ecom_missing")

    assert response.status_code == 404


def test_eval_run_lookup_reads_summary(tmp_path):
    eval_run_id = "eval_20260622063000_demo"
    target = tmp_path / eval_run_id
    target.mkdir()
    (target / "summary.json").write_text(
        json.dumps({"eval_run_id": eval_run_id, "pass_rate": 1.0}),
        encoding="utf-8",
    )

    response = _client().get(
        f"/api/ecommerce/eval/runs/{eval_run_id}",
        params={"output_dir": str(tmp_path)},
    )

    assert response.status_code == 200
    assert response.json()["eval_run_id"] == eval_run_id


def test_eval_run_lookup_returns_404_when_missing(tmp_path):
    """[FIX-4]/[FIX-6] unknown eval run is 404; output_dir is configurable."""

    response = _client().get(
        "/api/ecommerce/eval/runs/eval_missing",
        params={"output_dir": str(tmp_path)},
    )

    assert response.status_code == 404
