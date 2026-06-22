"""
导出三个标准 demo case（跨境电商选品研究）。

【正经注释】
对预定义的三个品类各跑一次 run_ecommerce_research（真实 Tavily 检索 + DeepSeek LLM 打分），
把每个 case 的 final_state 写成统一命名的 4 个文件（report.md / audit.json / quality.json /
evaluation.json）放进 case 目录，并在顶层生成 case-index.json 清单。
设计为可重复执行：--output-root 指定根目录，重跑会覆盖已有 case 文件夹。
report.md / audit.json / quality.json / evaluation.json 为"干净标准命名"（无 slug 前缀），
runner 自身的 <slug>-*.json 也写在同一目录（来自 output_dir），但 demo case 统一以标准命名为准。

【大白话注释】
跑三个固定的选品 demo，每个跑完都把报告 / 日志 / 质检 / 评分四份文件
用统一名字（report.md 这种）放到各自的小文件夹里，再生成一份总清单。
可以反复跑、覆盖旧结果，方便随时刷新 demo 数据给简历或评审看。
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import shutil
import sys
from pathlib import Path
from typing import Any

# 把仓库根目录加入 sys.path，保证从 scripts/ 里也能 import multi_agents / gpt_researcher
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 三个标准 demo case：slug 是目录名，title 是清单里展示用的标题
CASES: list[dict[str, Any]] = [
    {
        "slug": "portable-blender",
        "title": "Portable Blender",
        "query": "portable blender",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "standard",
    },
    {
        "slug": "pet-water-fountain",
        "title": "Pet Water Fountain",
        "query": "pet water fountain",
        "target_market": "US",
        "platforms": ["amazon", "reddit"],
        "depth": "standard",
    },
    {
        "slug": "standing-desk",
        "title": "Standing Desk",
        "query": "standing desk",
        "target_market": "US",
        "platforms": ["amazon", "google"],
        "depth": "deep",
    },
]


def _load_dotenv() -> None:
    """加载 .env，让 TAVILY_API_KEY / OPENAI_* 等检索器与 LLM 配置生效。"""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # 没有 python-dotenv 也允许继续（依赖系统环境变量）
        pass


def _write_case_files(case_dir: Path, slug: str, final_state: dict[str, Any]) -> None:
    """把一次研究的 final_state 写成 4 个标准命名文件，并清掉 runner 留下的 slug 前缀副本。

    runner 默认会在 output_dir（=本 case 目录）写出 <slug>-report.md /
    <slug>-audit.json / <slug>-quality.json / <slug>-evaluation.json。
    为了让 case 目录布局干净（只保留 report.md / audit.json / quality.json /
    evaluation.json 这 4 个标准名），写完标准文件后把这些 slug 前缀副本删掉。
    """
    case_dir.mkdir(parents=True, exist_ok=True)

    # report.md：final_report 原文
    report_text = final_state.get("final_report") or ""
    (case_dir / "report.md").write_text(report_text, encoding="utf-8")

    # audit.json：各 Agent 执行审计日志
    audit_log = final_state.get("audit_log") or []
    (case_dir / "audit.json").write_text(
        json.dumps(audit_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # quality.json：质量检查结果
    quality_check = final_state.get("quality_check") or {}
    (case_dir / "quality.json").write_text(
        json.dumps(quality_check, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # evaluation.json：评估摘要（runner 已经 build_evaluation_summary 后塞进 state）
    evaluation_summary = (
        final_state.get("evaluation_summary")
        # 兜底：万一没塞进去就现场构造一份
        or _build_evaluation_fallback(final_state)
    )
    (case_dir / "evaluation.json").write_text(
        json.dumps(evaluation_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 【正经注释】AgentOps 三件套（trace / human_review / run）也写成标准命名文件。
    # runner 默认会在 output_dir（=本 case 目录）写出 <slug>-trace.json /
    # <slug>-human-review.json / <slug>-run.json。这里对 trace / human-review 直接
    # 复制 runner 写好的 slug 前缀副本到标准命名（与 run.json 同口径，保证字节一致），
    # 不从 final_state 重新序列化——runner 落盘时已对缺失 state 字段做了兜底填充，
    # 磁盘上的那份才是 manifest artifact 链接指向的 canonical 副本。
    # 这两项是可选的：用 Path.exists() 判断 runner 是否产出过 slug 前缀文件，
    # 没产出就跳过，保持 manifest 链接与实际文件一致。
    for file_name in ("trace.json", "human-review.json"):
        canonical = case_dir / file_name
        if canonical.exists():
            # 标准 canonical 副本已存在则跳过（与 run.json 同口径）
            continue
        slug_prefixed = case_dir / f"{slug}-{file_name}"
        if slug_prefixed.exists():
            # 复用 runner 写好的 slug 前缀副本（字节级一致）
            try:
                canonical.write_text(
                    slug_prefixed.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            except OSError:
                # 读/写失败不阻断主流程：manifest 链接仍指向标准名，
                # 缺失文件由消费方自行容忍
                pass

    # run.json：由 runner 的 run_metadata 构造（run_id / output_paths / 评估摘要）。
    # final_state 里没有完整的 run_metadata（runner 在落盘时才组装），所以优先复用
    # runner 已经写好的 <slug>-run.json；若不存在则现场构造一份最小可用的。
    run_canonical = case_dir / "run.json"
    run_slug_prefixed = case_dir / f"{slug}-run.json"
    if not run_canonical.exists():
        if run_slug_prefixed.exists():
            # 复用 runner 写好的 run.json（含 output_paths + evaluation_summary）
            try:
                run_canonical.write_text(
                    run_slug_prefixed.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            except OSError:
                # 读失败不阻断主流程；下面兜底再构造一份
                pass
        else:
            # 兜底：runner 没写 run.json 时，用 state 现场拼一份最小 metadata
            run_metadata_fallback = {
                "run_id": final_state.get("run_id", ""),
                "query": final_state.get("query", ""),
                "target_market": final_state.get("target_market", ""),
                "output_paths": final_state.get("output_paths", {}),
                "evaluation_summary": evaluation_summary,
            }
            run_canonical.write_text(
                json.dumps(run_metadata_fallback, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    # 清理 runner 留下的 slug 前缀副本，保持 case 目录只有标准命名文件
    for suffix in (
        "report.md",
        "audit.json",
        "quality.json",
        "evaluation.json",
        "trace.json",
        "human-review.json",
        "run.json",
    ):
        slug_prefixed = case_dir / f"{slug}-{suffix}"
        if slug_prefixed.exists():
            try:
                slug_prefixed.unlink()
            except OSError:
                # 删除失败不影响主流程（最多多一份冗余文件）
                pass


def _build_evaluation_fallback(final_state: dict[str, Any]) -> dict[str, Any]:
    """若 runner 没在 state 里放 evaluation_summary，则现场调 evaluation 模块构造。"""
    try:
        from multi_agents.ecommerce.evaluation import build_evaluation_summary

        return build_evaluation_summary(final_state)
    except Exception:
        return {
            "overall_score": final_state.get("opportunity_score", {}).get(
                "overall_score", 0.0
            ),
            "quality_passed": final_state.get("quality_check", {}).get("passed", False),
        }


def _write_manifest(output_root: Path, entries: list[dict[str, Any]]) -> Path:
    """写顶层 case-index.json 清单。路径用 / 分隔（跨平台展示友好）。"""
    manifest_path = output_root / "case-index.json"
    manifest_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


async def _run_one_case(
    case: dict[str, Any], output_root: Path, force_clean: bool
) -> dict[str, Any]:
    """跑单个 demo case，返回清单条目。"""
    slug = case["slug"]
    case_dir = output_root / slug

    # 重跑前清掉旧目录，避免残留文件干扰（runner 的 slug 前缀文件也会被一并清除）
    if force_clean and case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)

    # 延迟导入：放到函数内，保证 scripts/ 目录在被 import 时也能找到项目根
    from multi_agents.ecommerce.llm_helper import default_llm_fn
    from multi_agents.ecommerce.runner import run_ecommerce_research

    started_at = datetime.datetime.now().isoformat(timespec="seconds")
    print(
        f"[demo] >>> case='{slug}' query='{case['query']}' "
        f"depth={case['depth']} platforms={case['platforms']} -> {case_dir}",
        flush=True,
    )

    final_state = await run_ecommerce_research(
        query=case["query"],
        target_market=case["target_market"],
        platforms=case["platforms"],
        depth=case["depth"],
        # output_dir 直接指向 case 目录，runner 自身的 <slug>-*.json 也落在这里
        output_dir=str(case_dir),
        # 启用 LLM 打分（DeepSeek），不传则退回纯规则
        llm_fn=default_llm_fn,
    )

    _write_case_files(case_dir, slug, final_state)

    finished_at = datetime.datetime.now().isoformat(timespec="seconds")
    eval_summary = final_state.get("evaluation_summary") or {}
    print(
        f"[demo] <<< case='{slug}' done. "
        f"score={eval_summary.get('overall_score')} "
        f"evidence={eval_summary.get('evidence_count')} "
        f"fallback={eval_summary.get('fallback_count')}",
        flush=True,
    )

    # 把条目构造抽到独立函数，方便单测覆盖（含 governance 字段透传校验）
    return _build_success_entry(
        case,
        eval_summary,
        started_at=started_at,
        finished_at=finished_at,
    )


def _build_error_entry(case: dict[str, Any], error_msg: str) -> dict[str, Any]:
    """单个 case 执行失败时构造的清单条目。

    保留 slug / title / query 等元数据，让清单行仍然可读；
    额外加 status='error' 与 error 字段，便于事后排查。
    成功路径不会带这两个字段，所以已提交的 manifest 行形状不变。
    """
    slug = case["slug"]
    return {
        "slug": slug,
        "title": case["title"],
        "query": case["query"],
        "target_market": case["target_market"],
        "platforms": case["platforms"],
        "depth": case["depth"],
        "status": "error",
        "error": error_msg,
    }


def _build_success_entry(
    case: dict[str, Any],
    summary: dict[str, Any],
    *,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    """单个 case 成功时的清单条目。

    【正经注释】
    把 case 元数据 + 评估摘要拼成统一形状的清单行。summary 整体透传（不做字段白名单），
    这样 evaluation_summary 里的 governance 指标（retry_count / llm_call_count /
    estimated_cost_usd / policy_block_count …）会原样进入 manifest，供前端评估页展示。

    【大白话注释】
    把一个跑成功的 demo 拼成清单里的一行，评估摘要整包塞进去不挑字段，
    这样后面那些"重试次数 / LLM 调用次数 / 花了多少钱"之类的治理指标都不会丢，
    能直接在评估页上显示出来。
    """
    slug = case["slug"]
    entry: dict[str, Any] = {
        "slug": slug,
        "title": case["title"],
        "query": case["query"],
        "target_market": case["target_market"],
        "platforms": case["platforms"],
        "depth": case["depth"],
        "report": f"/outputs/ecommerce/demo-cases/{slug}/report.md",
        "evaluation": f"/outputs/ecommerce/demo-cases/{slug}/evaluation.json",
        "audit": f"/outputs/ecommerce/demo-cases/{slug}/audit.json",
        "quality": f"/outputs/ecommerce/demo-cases/{slug}/quality.json",
        "trace": f"/outputs/ecommerce/demo-cases/{slug}/trace.json",
        "human_review": f"/outputs/ecommerce/demo-cases/{slug}/human-review.json",
        "run": f"/outputs/ecommerce/demo-cases/{slug}/run.json",
        "summary": summary,
    }
    # 时间戳是可选的（单测构造时不传），只在给了的时候写进去，保持条目形状稳定
    if started_at is not None:
        entry["started_at"] = started_at
    if finished_at is not None:
        entry["finished_at"] = finished_at
    return entry


async def _run_all(output_root: Path, force_clean: bool) -> list[dict[str, Any]]:
    """串行跑三个 case（避免并发把 Tavily / DeepSeek 速率打爆）。

    每个 case 独立 try/except：某一个 case 抛异常（Tavily 限流、DeepSeek 5xx、
    网络抖动等）不会中断其它 case，也不会阻止最后的 manifest 落盘。
    失败的 case 以 status='error' 条目进入清单，便于事后重跑。
    """
    entries: list[dict[str, Any]] = []
    for case in CASES:
        try:
            entry = await _run_one_case(case, output_root, force_clean)
        except Exception as exc:  # noqa: BLE001 — 隔离任意失败，逐个记录后继续
            # 不让单个 case 的失败拖垮整批；记录错误条目并继续下一个
            error_msg = f"{type(exc).__name__}: {exc}"
            print(
                f"[demo] !!! case='{case['slug']}' FAILED, continuing. "
                f"error={error_msg}",
                flush=True,
            )
            entry = _build_error_entry(case, error_msg)
        entries.append(entry)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="export_ecommerce_demo_cases",
        description="导出三个标准跨境电商选品 demo case（真实检索 + LLM 打分）",
    )
    parser.add_argument(
        "--output-root",
        default="outputs/ecommerce/demo-cases",
        help="demo case 根目录，默认 outputs/ecommerce/demo-cases",
    )
    parser.add_argument(
        "--keep-old",
        action="store_true",
        help="重跑时保留旧 case 目录里的残留文件（默认会先清空）",
    )
    args = parser.parse_args()

    _load_dotenv()

    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    # try/finally 保证：即便 _run_all 自身抛出意外异常（例如 event loop 启动失败），
    # 已经收集到的 entries 也会落盘成 manifest。正常情况下 _run_all 内部已对每个
    # case 做了 try/except，不会走到 finally 的兜底分支。
    entries: list[dict[str, Any]] = []
    try:
        entries = asyncio.run(_run_all(output_root, force_clean=not args.keep_old))
    finally:
        # 只要收集到任何条目就落盘，绝不让单个失败把整份清单吞掉
        if entries:
            _write_manifest(output_root, entries)

    manifest_path = output_root / "case-index.json"
    print(f"\n[demo] manifest -> {manifest_path}")
    print(f"[demo] {len(entries)} cases exported under {output_root}")
    for entry in entries:
        status = entry.get("status")
        if status == "error":
            # 失败条目没有 summary，单独打印错误，方便定位
            print(f"  - {entry['slug']:<20} status=ERROR error={entry.get('error')}")
        else:
            s = entry.get("summary") or {}
            print(
                f"  - {entry['slug']:<20} score={s.get('overall_score')} "
                f"evidence={s.get('evidence_count')} report={entry['report']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
