"""File-backed run artifact store for ecommerce research.

【正经注释】
把 runner 落盘的 *-run.json 作为索引文件，按 run_id 反查同目录下的 trace /
human-review / evaluation / report 等产物，提供给 API 层（GET /runs/{run_id}）。
load_run/save_human_review 对未知 run_id 或缺失路径统一抛 FileNotFoundError，
让 API 层捕获后转成 HTTP 404（FIX-4），避免泄露 500。

【大白话注释】
给每次研究建一个"档案室"：拿着 run_id（订单号）去 outputs/ecommerce/ 里
翻出当时的报告、评审、评分。找不着就抛 FileNotFoundError，让接口返回 404。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _read_json(path: Path, fallback: Any) -> Any:
    """读 JSON 文件；不存在返回 fallback（不抛错，让缺字段的 run 也能部分返回）。"""
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_path(path_value: str | None, fallback: Any) -> Any:
    """按【字符串值】先判空再 Path() —— FIX-5：Path("") 会变成 Path(".")（truthy），
    导致"路径缺失"被误判为"路径指向当前目录"，进而触发 IsADirectoryError 泄露 500。
    传 None/"" 一律直接返回 fallback，绝不构造 Path("")。
    """
    if not path_value:
        return fallback
    return _read_json(Path(path_value), fallback)


def _find_run_file(run_id: str, output_dir: str | Path) -> Path:
    """在 output_dir 下扫所有 *-run.json，匹配 run_id 字段；找不到抛 FileNotFoundError。"""
    root = Path(output_dir)
    for path in root.glob("*-run.json"):
        data = _read_json(path, {})
        if data.get("run_id") == run_id:
            return path
    raise FileNotFoundError(f"ecommerce run not found: {run_id}")


def _read_text(path_value: str | None) -> str:
    """读文本文件（报告是 Markdown）；缺路径或文件不存在都返回空串。"""
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_run(
    run_id: str,
    *,
    output_dir: str | Path = "outputs/ecommerce",
) -> dict[str, Any]:
    """按 run_id 加载本次研究的全部可读产物（元数据 + trace + 评审 + 评估 + 报告）。

    返回 dict 会把 run.json 里的所有字段（run_id/output_paths/evaluation_summary/...）
    原样铺开，再用 agent_trace/human_review/evaluation_summary/report 覆盖/补充。
    """
    run_path = _find_run_file(run_id, output_dir)
    metadata = _read_json(run_path, {})
    paths = metadata.get("output_paths", {})
    return {
        **metadata,
        "agent_trace": _read_json_path(paths.get("trace"), []),
        "human_review": _read_json_path(
            paths.get("human_review"),
            {"review_status": "pending"},
        ),
        "evaluation_summary": _read_json_path(
            paths.get("evaluation"),
            metadata.get("evaluation_summary", {}),
        ),
        "report": _read_text(paths.get("report")),
    }


def save_human_review(
    run_id: str,
    review: Mapping[str, Any],
    *,
    output_dir: str | Path = "outputs/ecommerce",
) -> dict[str, Any]:
    """把人工评审（HITL）写回本次 run 的 human-review.json。

    FIX-5：必须先检查【原始字符串】path_value 是否为空，再 Path() ——
    否则 Path("") → Path(".")，`if not review_path` 永远不触发，会以 IsADirectoryError 泄露 500。
    路径缺失时抛 FileNotFoundError，API 层据此返回 404。
    """
    metadata = _read_json(_find_run_file(run_id, output_dir), {})
    paths = metadata.get("output_paths", {})
    review_path_value = paths.get("human_review")
    if not review_path_value:
        raise FileNotFoundError(f"human review path missing for run: {run_id}")
    review_path = Path(review_path_value)
    payload = dict(review)
    payload.setdefault("review_status", "pending")
    review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
