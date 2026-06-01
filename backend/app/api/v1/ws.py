"""
WebSocket 端点：实时推送评测任务和优化任务的进度。
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import async_session
from app.models.eval_task import EvalTask
from app.models.optimization import OptimizationTask

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/eval/{task_id}")
async def ws_eval_progress(websocket: WebSocket, task_id: int):
    """评测任务实时进度推送"""
    await websocket.accept()
    try:
        while True:
            async with async_session() as db:
                result = await db.execute(
                    select(EvalTask).where(EvalTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if not task:
                    await websocket.send_json({"error": "任务不存在"})
                    break

                await websocket.send_json({
                    "type": "eval_progress",
                    "task_id": task_id,
                    "status": task.status,
                    "completed_items": task.completed_items or 0,
                    "total_items": task.total_items or 0,
                    "overall_score": task.overall_score or 0.0,
                    "error_message": task.error_message or "",
                })

                if task.status in ("completed", "failed", "cancelled"):
                    break

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket eval/%d 异常", task_id)


@router.websocket("/optimization/{task_id}")
async def ws_optimization_progress(websocket: WebSocket, task_id: int):
    """优化任务实时进度推送"""
    await websocket.accept()
    try:
        while True:
            async with async_session() as db:
                result = await db.execute(
                    select(OptimizationTask).where(OptimizationTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if not task:
                    await websocket.send_json({"error": "任务不存在"})
                    break

                await websocket.send_json({
                    "type": "opt_progress",
                    "task_id": task_id,
                    "status": task.status,
                    "current_round": task.current_round or 0,
                    "max_rounds": task.max_rounds,
                    "best_score": task.best_score or 0.0,
                    "baseline_score": task.baseline_score or 0.0,
                    "score_history_json": task.score_history_json or "[]",
                    "best_prompt": task.best_prompt or "",
                    "error_message": task.error_message or "",
                })

                if task.status in ("completed", "failed", "cancelled"):
                    break

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket optimization/%d 异常", task_id)
