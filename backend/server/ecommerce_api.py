"""
EcomResearcher 的 FastAPI 路由（POST 同步接口 + WebSocket 流式进度）。

【正经注释】
以 APIRouter 形式提供，由 server/app.py 通过 include_router 注册，不侵入主路由文件。
- POST /api/ecommerce/research：同步执行一次选品调研，返回报告/评分/质检/审计 JSON。
- WS  /ws/ecommerce：客户端连入后发 {query,...}，服务端按阶段流式推送进度，最终回传完整结果。

【大白话注释】
把跨境电商研究能力暴露成 HTTP 接口：
- 一个 POST 接口：发品类关键词，等一会，拿回完整结果。
- 一个 WebSocket 接口：连上后能实时看到"规划完成/研究完成/评分完成"等进度。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from multi_agents.ecommerce.llm_helper import default_llm_fn
from multi_agents.ecommerce.runner import run_ecommerce_research
from multi_agents.ecommerce.runtime.run_store import load_run, save_human_review

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ecommerce"])


class EcommerceRequest(BaseModel):
    """POST /api/ecommerce/research 请求体。"""

    query: str
    target_market: str = "US"
    # 【正经注释】FIX-7：可变默认值必须用 Field(default_factory=...)，
    # 否则 Pydantic 会把同一个 list 实例共享给所有请求（典型 mutable-default 陷阱）。
    # 【大白话注释】别直接写 = ["amazon","google"]，那样子所有请求会共用同一个列表；
    # 用 Field(default_factory=...) 每次都新建一份，互不干扰。
    platforms: list[str] = Field(default_factory=lambda: ["amazon", "google"])
    depth: str = "standard"
    use_llm: bool = True
    # MCP 相关字段（FIX-3：trace 永远开，所以没有 trace_enabled 开关）：
    # Task 4 只是把这三个透传给 runner（runner 只记进 state），真正接线在 Task 8。
    mcp_enabled: bool = False
    mcp_strategy: str = "fast"
    mcp_configs: list[dict[str, Any]] = Field(default_factory=list)


def _summarize(result: dict) -> dict:
    """从最终 state 抽取接口返回字段。"""
    return {
        "query": result.get("query"),
        "target_market": result.get("target_market"),
        "trend_result": result.get("trend_result"),
        "competitor_result": result.get("competitor_result"),
        "review_result": result.get("review_result"),
        "opportunity_score": result.get("opportunity_score"),
        "quality_check": result.get("quality_check"),
        "audit_log": result.get("audit_log"),
        "report": result.get("final_report"),
        "output_paths": result.get("output_paths"),
        # 【正经注释】agentops / HITL / MCP 相关字段：全部 .get(...) 兜底，
        # 让旧版本 runner（没写这些字段）也能正常返回，不会 KeyError。
        "run_id": result.get("run_id"),
        "agent_trace": result.get("agent_trace", []),
        "evaluation_summary": result.get("evaluation_summary", {}),
        "human_review": result.get("human_review", {}),
        "eval_result": result.get("eval_result", {}),
        "mcp_context": result.get("mcp_context", {}),
    }


@router.post("/api/ecommerce/research")
async def ecommerce_research(req: EcommerceRequest) -> dict:
    """同步执行一次跨境电商选品调研。"""
    logger.info(f"[ecommerce] POST research query='{req.query}' depth={req.depth}")
    result = await run_ecommerce_research(
        query=req.query,
        target_market=req.target_market,
        platforms=req.platforms,
        depth=req.depth,
        llm_fn=default_llm_fn if req.use_llm else None,
        # 【正经注释】Task 4 仅把 MCP 三个 kwarg 透传给 runner（runner 只记进 state["mcp_context"]）；
        # 真正按 mcp_enabled 切到 MCP 检索的工作在 Task 8。
        mcp_enabled=req.mcp_enabled,
        mcp_strategy=req.mcp_strategy,
        mcp_configs=req.mcp_configs,
    )
    return _summarize(result)


@router.get("/api/ecommerce/runs/{run_id}")
async def ecommerce_run(run_id: str) -> dict:
    """按 run_id 反查本次研究的全部产物（trace/评审/评估/报告）。

    【正经注释】FIX-4：run_store.load_run 对未知 run_id 抛 FileNotFoundError，
    必须在这里捕获并转成 HTTP 404，否则会泄露 500（FastAPI 默认未捕获异常）。
    """
    try:
        return load_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/ecommerce/runs/{run_id}/human-review")
async def ecommerce_human_review(run_id: str, review: dict[str, Any]) -> dict:
    """把人工评审（HITL）写回本次 run 的 human-review.json。

    【正经注释】FIX-4 + FIX-5：save_human_review 在 run 不存在或 human_review 路径缺失时
    都抛 FileNotFoundError（FIX-5：先判原始字符串再 Path()，避免 Path("") → IsADirectoryError 泄露 500），
    这里统一捕获转 404。
    """
    try:
        saved = save_human_review(run_id, review)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"run_id": run_id, "human_review": saved}


@router.websocket("/ws/ecommerce")
async def ecommerce_websocket(websocket: WebSocket) -> None:
    """WebSocket 流式进度：收 {query,...} → 逐阶段推送 → 最终回传完整结果。"""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        query = data.get("query")
        if not query:
            await websocket.send_json({"event": "error", "error": "missing query"})
            await websocket.close()
            return

        async def progress(event: str, payload: dict) -> None:
            await websocket.send_json({"event": event, **payload})

        result = await run_ecommerce_research(
            query=query,
            target_market=data.get("target_market", "US"),
            platforms=data.get("platforms", ["amazon", "google"]),
            depth=data.get("depth", "standard"),
            llm_fn=default_llm_fn if data.get("use_llm", True) else None,
            progress_callback=progress,
        )
        await websocket.send_json(
            {
                "event": "done",
                **_summarize(result),
            }
        )
    except WebSocketDisconnect:
        logger.info("[ecommerce] websocket disconnected")
    except Exception as exc:  # 任何异常都回传，避免前端一直挂起
        logger.error(f"[ecommerce] websocket error: {exc}")
        try:
            await websocket.send_json({"event": "error", "error": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
