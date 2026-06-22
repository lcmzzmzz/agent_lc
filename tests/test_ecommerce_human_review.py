import json

import pytest

from multi_agents.ecommerce.runtime.run_store import load_run, save_human_review


def _write_run_fixture(root):
    run_id = "ecom_20260622063000_portable-blender_abc123"
    trace = [{"run_id": run_id, "node": "planner"}]
    review = {"review_status": "pending"}
    evaluation = {"overall_score": 6.5}
    report = "# Report"
    paths = {
        "trace": str(root / "portable-blender-trace.json"),
        "human_review": str(root / "portable-blender-human-review.json"),
        "evaluation": str(root / "portable-blender-evaluation.json"),
        "report": str(root / "portable-blender-report.md"),
    }
    (root / "portable-blender-trace.json").write_text(json.dumps(trace), encoding="utf-8")
    (root / "portable-blender-human-review.json").write_text(json.dumps(review), encoding="utf-8")
    (root / "portable-blender-evaluation.json").write_text(json.dumps(evaluation), encoding="utf-8")
    (root / "portable-blender-report.md").write_text(report, encoding="utf-8")
    (root / "portable-blender-run.json").write_text(
        json.dumps({"run_id": run_id, "output_paths": paths}),
        encoding="utf-8",
    )
    return run_id


def test_load_run_reads_file_backed_artifacts(tmp_path):
    run_id = _write_run_fixture(tmp_path)

    payload = load_run(run_id, output_dir=tmp_path)

    assert payload["run_id"] == run_id
    assert payload["agent_trace"][0]["node"] == "planner"
    assert payload["human_review"]["review_status"] == "pending"
    assert payload["evaluation_summary"]["overall_score"] == 6.5
    assert payload["report"] == "# Report"


def test_load_run_raises_filenotfound_for_unknown_run(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_run("ecom_unknown", output_dir=tmp_path)


def test_save_human_review_updates_review_file(tmp_path):
    run_id = _write_run_fixture(tmp_path)
    review = {
        "review_status": "revised",
        "score_overrides": {
            "trend_score": {
                "value": 6.5,
                "original_value": 7.4,
                "reason": "mixed evidence",
            }
        },
    }

    saved = save_human_review(run_id, review, output_dir=tmp_path)
    loaded = load_run(run_id, output_dir=tmp_path)

    assert saved["review_status"] == "revised"
    assert loaded["human_review"]["score_overrides"]["trend_score"]["value"] == 6.5


def test_load_run_reads_visual_result(tmp_path):
    from multi_agents.ecommerce.runtime.run_store import load_run

    run_id = "ecom_20260623090000_portable-blender_abc123"
    visual_path = tmp_path / "portable-blender-visual" / "visual-assets.json"
    visual_path.parent.mkdir()
    visual_path.write_text(
        json.dumps({"status": "success", "assets": [{"asset_id": "visual_product_01"}]}),
        encoding="utf-8",
    )
    run_path = tmp_path / "portable-blender-run.json"
    run_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "output_paths": {"visual_assets": str(visual_path)},
                "evaluation_summary": {},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_run(run_id, output_dir=tmp_path)

    assert loaded["visual_result"]["status"] == "success"
    assert loaded["visual_result"]["assets"][0]["asset_id"] == "visual_product_01"


def test_save_human_review_raises_when_review_path_missing(tmp_path):
    """[FIX-5] Missing human_review path must become a FileNotFoundError,
    so the API layer can consistently return 404 instead of leaking a 500.
    """

    run_id = "ecom_20260622063000_portable-blender_abc123"
    (tmp_path / "portable-blender-run.json").write_text(
        json.dumps({"run_id": run_id, "output_paths": {}}),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        save_human_review(run_id, {"review_status": "approved"}, output_dir=tmp_path)
