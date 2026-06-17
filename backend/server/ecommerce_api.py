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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from multi_agents.ecommerce.llm_helper import default_llm_fn
from multi_agents.ecommerce.runner import run_ecommerce_research

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ecommerce"])


class EcommerceRequest(BaseModel):
    """POST /api/ecommerce/research 请求体。"""

    query: str
    target_market: str = "US"
    platforms: list[str] = ["amazon", "google"]
    depth: str = "standard"
    use_llm: bool = True


def _summarize(result: dict) -> dict:
    """从最终 state 抽取接口返回字段。"""
    return {
        "query": result.get("query"),
        "target_market": result.get("target_market"),
        "opportunity_score": result.get("opportunity_score"),
        "quality_check": result.get("quality_check"),
        "audit_log": result.get("audit_log"),
        "report": result.get("final_report"),
        "output_paths": result.get("output_paths"),
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
    )
    return _summarize(result)


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
            use_llm=data.get("use_llm", True),
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
