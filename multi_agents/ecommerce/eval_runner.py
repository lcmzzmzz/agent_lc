"""Batch evaluation utilities for ecommerce golden cases."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

from multi_agents.ecommerce.runner import run_ecommerce_research

RunFn = Callable[..., Awaitable[dict[str, Any]]]


def load_eval_cases(path: str | Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text:
            cases.append(json.loads(text))
    return cases


def _in_range(value: float, bounds: list[float]) -> bool:
    return float(bounds[0]) <= float(value) <= float(bounds[1])


def _contains_all(text: str, required: list[str]) -> bool:
    lowered = text.lower()
    return all(item.lower() in lowered for item in required)


def _citation_count(report: str) -> int:
    return report.count("http://") + report.count("https://")


def evaluate_case_result(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    expected = case.get("expected", {})
    report = str(result.get("final_report", ""))
    review_text = " ".join(result.get("review_result", {}).get("pain_points", []))
    checks = {
        "trend_range": _in_range(
            result.get("trend_result", {}).get("trend_score", 0.0),
            expected.get("trend_range", [0.0, 10.0]),
        ),
        "competition_range": _in_range(
            result.get("competitor_result", {}).get("competition_score", 0.0),
            expected.get("competition_range", [0.0, 10.0]),
        ),
        "pain_point_range": _in_range(
            result.get("review_result", {}).get("pain_point_score", 0.0),
            expected.get("pain_point_range", [0.0, 10.0]),
        ),
        "overall_range": _in_range(
            result.get("opportunity_score", {}).get("overall_score", 0.0),
            expected.get("overall_range", [0.0, 10.0]),
        ),
        "must_have_risks": _contains_all(
            report,
            expected.get("must_have_risks", []),
        ),
        "must_have_pain_points": _contains_all(
            f"{review_text}\n{report}",
            expected.get("must_have_pain_points", []),
        ),
        "min_citations": _citation_count(report) >= int(expected.get("min_citations", 0)),
        "max_fallback_count": int(
            result.get("evaluation_summary", {}).get("fallback_count", 0)
        )
        <= int(expected.get("max_fallback_count", 99)),
        "quality_passed": bool(result.get("quality_check", {}).get("passed", False)),
    }
    passed_count = sum(1 for passed in checks.values() if passed)
    score = round(passed_count / len(checks), 2) if checks else 0.0
    return {
        "case_id": case.get("case_id", ""),
        "run_id": result.get("run_id", ""),
        "passed": all(checks.values()),
        "score": score,
        "checks": checks,
    }


async def run_eval_cases(
    cases_path: str | Path,
    *,
    output_dir: str | Path = "outputs/ecommerce/eval-runs",
    run_fn: RunFn = run_ecommerce_research,
) -> dict[str, Any]:
    cases = load_eval_cases(cases_path)
    eval_run_id = f"eval_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    target = Path(output_dir) / eval_run_id
    target.mkdir(parents=True, exist_ok=True)
    case_results: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for case in cases:
        result = await run_fn(
            query=case["query"],
            target_market=case.get("target_market", "US"),
            platforms=case.get("platforms", ["amazon", "google"]),
            depth=case.get("depth", "standard"),
        )
        eval_result = evaluate_case_result(case, result)
        result["eval_result"] = eval_result
        case_results.append(eval_result)
        manifest.append(
            {
                "case_id": case.get("case_id", ""),
                "title": case.get("case_id", ""),
                "query": case.get("query", ""),
                "summary": {
                    **result.get("evaluation_summary", {}),
                    "eval_passed": eval_result["passed"],
                    "eval_score": eval_result["score"],
                },
            }
        )
    passed_cases = sum(1 for row in case_results if row["passed"])
    summary = {
        "eval_run_id": eval_run_id,
        "total_cases": len(case_results),
        "passed_cases": passed_cases,
        "pass_rate": round(passed_cases / len(case_results), 2) if case_results else 0.0,
        "cases": case_results,
    }
    (target / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "cases.json").write_text(
        json.dumps(case_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "case-index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
