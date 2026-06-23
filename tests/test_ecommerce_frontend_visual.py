from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ecommerce_page_contains_visual_controls_and_panel():
    html = (ROOT / "frontend" / "ecommerce.html").read_text(encoding="utf-8")

    assert 'id="visualEnabled"' in html
    assert 'id="visualImageCount"' in html
    assert 'id="visualCard"' in html
    assert "renderVisualResult" in html
    assert "visual_enabled" in html
    assert "visual_image_count" in html


def test_review_page_contains_visual_review_controls():
    html = (ROOT / "frontend" / "ecommerce-review.html").read_text(encoding="utf-8")

    assert 'id="visualReviewBody"' in html
    assert "visual_reviews" in html
    assert "approved" in html
    assert "needs_edit" in html


def test_eval_page_contains_visual_metrics():
    html = (ROOT / "frontend" / "ecommerce-eval.html").read_text(encoding="utf-8")

    assert "visual_asset_count" in html
    assert "visual_failed_asset_count" in html
    assert "visual_status" in html
