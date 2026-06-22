import json

import pytest

from multi_agents.ecommerce.eval_runner import (
    evaluate_case_result,
    load_eval_cases,
    run_eval_cases,
)


def _case():
    return {
        "case_id": "portable-blender-us-standard",
        "query": "portable blender",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "standard",
        "expected": {
            "trend_range": [6.0, 8.0],
            "competition_range": [4.0, 7.0],
            "pain_point_range": [6.0, 9.0],
            "overall_range": [5.5, 8.0],
            "must_have_risks": ["battery", "leakage"],
            "must_have_pain_points": ["cleaning"],
            "min_citations": 2,
            "max_fallback_count": 1,
        },
    }


def _result():
    return {
        "run_id": "ecom_20260622063000_portable-blender_abc123",
        "trend_result": {"trend_score": 6.8},
        "competitor_result": {"competition_score": 5.8},
        "review_result": {
            "pain_point_score": 7.4,
            "pain_points": ["cleaning is difficult", "battery life is short"],
        },
        "opportunity_score": {"overall_score": 6.6},
        "quality_check": {"passed": True, "citation_coverage": 0.8},
        "evaluation_summary": {"fallback_count": 0, "evidence_count": 4},
        "final_report": "Battery risk and leakage risk are cited.\nhttps://a\nhttps://b",
    }


def test_load_eval_cases_reads_jsonl(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(_case()) + "\n", encoding="utf-8")

    cases = load_eval_cases(path)

    assert cases[0]["case_id"] == "portable-blender-us-standard"


def test_evaluate_case_result_passes_matching_result():
    eval_result = evaluate_case_result(_case(), _result())

    assert eval_result["case_id"] == "portable-blender-us-standard"
    assert eval_result["passed"] is True
    assert eval_result["checks"]["trend_range"] is True
    assert eval_result["checks"]["must_have_risks"] is True
    assert eval_result["checks"]["min_citations"] is True
    assert eval_result["score"] >= 0.8


def test_evaluate_case_result_reports_failed_checks():
    result = _result()
    result["trend_result"]["trend_score"] = 9.5
    result["final_report"] = "No risk citations"

    eval_result = evaluate_case_result(_case(), result)

    assert eval_result["passed"] is False
    assert eval_result["checks"]["trend_range"] is False
    assert eval_result["checks"]["must_have_risks"] is False


@pytest.mark.asyncio
async def test_run_eval_cases_writes_summary(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_case()) + "\n", encoding="utf-8")

    async def fake_run(**kwargs):
        return _result()

    summary = await run_eval_cases(cases_path, output_dir=tmp_path, run_fn=fake_run)

    assert summary["total_cases"] == 1
    assert summary["passed_cases"] == 1
    assert summary["pass_rate"] == 1.0
    assert (tmp_path / summary["eval_run_id"] / "summary.json").exists()
    assert (tmp_path / summary["eval_run_id"] / "case-index.json").exists()


@pytest.mark.asyncio
async def test_run_eval_cases_persists_eval_result_into_case_artifacts(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(json.dumps(_case()) + "\n", encoding="utf-8")
    evaluation_path = tmp_path / "portable-blender-evaluation.json"
    run_path = tmp_path / "portable-blender-run.json"
    evaluation_path.write_text(json.dumps({"eval_passed": None}), encoding="utf-8")
    run_path.write_text(
        json.dumps(
            {
                "run_id": "ecom_20260622063000_portable-blender_abc123",
                "output_paths": {
                    "evaluation": str(evaluation_path),
                    "run": str(run_path),
                },
                "evaluation_summary": {"eval_passed": None},
            }
        ),
        encoding="utf-8",
    )

    async def fake_run(**kwargs):
        result = _result()
        result["output_paths"] = {
            "evaluation": str(evaluation_path),
            "run": str(run_path),
        }
        return result

    summary = await run_eval_cases(cases_path, output_dir=tmp_path, run_fn=fake_run)

    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    run_meta = json.loads(run_path.read_text(encoding="utf-8"))
    assert summary["cases"][0]["passed"] is True
    assert evaluation["eval_passed"] is True
    assert evaluation["eval_score"] == 1.0
    assert run_meta["evaluation_summary"]["eval_passed"] is True
    assert run_meta["eval_result"]["passed"] is True
