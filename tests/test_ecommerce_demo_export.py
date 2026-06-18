"""Tests for ecommerce demo case export manifest helpers."""

from scripts.export_ecommerce_demo_cases import _build_error_entry


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
