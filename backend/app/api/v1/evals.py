import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db, async_session
from app.core.deps import get_current_user, require_task_executor
from app.models.user import User
from app.models.eval_task import EvalTask, EvalResult
from app.models.dataset import Dataset, DatasetItem
from app.schemas.eval import EvalTaskCreate, EvalTaskResponse, EvalResultResponse
from app.schemas.common import PaginatedResponse
from .demo_data import DEMO_EVAL_TASKS, get_demo_list, paginated
from app.utils.audit import audit_log, ACTION_EVAL_CREATE, ACTION_EVAL_START, \
    ACTION_EVAL_CANCEL, ACTION_EVAL_DELETE

router = APIRouter(tags=["evals"])


@router.get("/", response_model=PaginatedResponse)
async def list_eval_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None, description="Filter by status"),
    project_id: int = Query(None, description="Filter by project"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = select(EvalTask)
        count_query = select(func.count(EvalTask.id))

        if status:
            query = query.where(EvalTask.status == status)
            count_query = count_query.where(EvalTask.status == status)
        if project_id is not None:
            query = query.where(EvalTask.project_id == project_id)
            count_query = count_query.where(EvalTask.project_id == project_id)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        result = await db.execute(
            query.offset((page - 1) * page_size).limit(page_size).order_by(EvalTask.id.desc())
        )
        tasks = result.scalars().all()

        items = [
            EvalTaskResponse(
                id=t.id,
                name=t.name,
                project_id=t.project_id,
                model_id=t.model_id,
                dataset_id=t.dataset_id,
                metric_ids=t.metric_ids,
                prompt_content=t.prompt_content,
                prompt_id=t.prompt_id,
                status=t.status,
                schedule_type=t.schedule_type,
                cron_expression=t.cron_expression,
                total_items=t.total_items,
                completed_items=t.completed_items,
                overall_score=t.overall_score,
                error_message=t.error_message,
                started_at=t.started_at,
                finished_at=t.finished_at,
                created_by=t.created_by,
                created_at=t.created_at,
            )
            for t in tasks
        ]

        total_pages = (total + page_size - 1) // page_size
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except HTTPException:
        raise
    except Exception:
        items, total, _, _, total_pages = get_demo_list(DEMO_EVAL_TASKS, page, page_size)
        return paginated([EvalTaskResponse(**item) for item in items], total, page, page_size, total_pages)


@router.get("/{task_id}", response_model=EvalTaskResponse)
async def get_eval_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(EvalTask).where(EvalTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")

        return EvalTaskResponse(
            id=task.id,
            name=task.name,
            project_id=task.project_id,
            model_id=task.model_id,
            dataset_id=task.dataset_id,
            metric_ids=task.metric_ids,
            prompt_content=task.prompt_content,
            prompt_id=task.prompt_id,
            status=task.status,
            schedule_type=task.schedule_type,
            cron_expression=task.cron_expression,
            total_items=task.total_items,
            completed_items=task.completed_items,
            overall_score=task.overall_score,
            error_message=task.error_message,
            started_at=task.started_at,
            finished_at=task.finished_at,
            created_by=task.created_by,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        for task in DEMO_EVAL_TASKS:
            if task["id"] == task_id:
                return EvalTaskResponse(**task)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")


@router.post("/", response_model=EvalTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_eval_task(
    req: EvalTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_task_executor),
):
    try:
        # 校验数据集存在且已发布
        dataset_result = await db.execute(select(Dataset).where(Dataset.id == req.dataset_id))
        dataset = dataset_result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
        if dataset.status not in ("approved", "published"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据集状态为 '{dataset.status}'，只有已审核/已发布的数据集才能用于评测")

        # 校验指标均已审核
        from app.models.metric import Metric
        metric_ids = [int(mid) for mid in req.metric_ids.split(",") if mid.strip()]
        if metric_ids:
            metric_result = await db.execute(select(Metric).where(Metric.id.in_(metric_ids)))
            metrics = metric_result.scalars().all()
            for m in metrics:
                if m.status != "approved":
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"评测标准 '{m.name}' 状态为 '{m.status}'，只有已审核的标准才能用于评测")

        task = EvalTask(
            name=req.name,
            project_id=req.project_id,
            model_id=req.model_id,
            dataset_id=req.dataset_id,
            metric_ids=req.metric_ids or "",
            prompt_content=req.prompt_content or "",
            prompt_id=req.prompt_id,
            schedule_type=req.schedule_type or "immediate",
            cron_expression=req.cron_expression or "",
            total_items=dataset.item_count,
            created_by=current_user.id,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_EVAL_CREATE, target_type="eval_task",
                        target_id=task.id, detail=f"创建评估任务: {task.name}")

        return EvalTaskResponse(
            id=task.id,
            name=task.name,
            project_id=task.project_id,
            model_id=task.model_id,
            dataset_id=task.dataset_id,
            metric_ids=task.metric_ids,
            prompt_content=task.prompt_content,
            prompt_id=task.prompt_id,
            status=task.status,
            schedule_type=task.schedule_type,
            cron_expression=task.cron_expression,
            total_items=task.total_items,
            completed_items=task.completed_items,
            overall_score=task.overall_score,
            error_message=task.error_message,
            started_at=task.started_at,
            finished_at=task.finished_at,
            created_by=task.created_by,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.post("/{task_id}/start", response_model=EvalTaskResponse)
async def start_eval_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_task_executor),
):
    import logging
    logger = logging.getLogger(__name__)

    try:
        # 1. 查询评测任务
        result = await db.execute(select(EvalTask).where(EvalTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")

        if task.status not in ("pending", "failed"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无法启动状态为 '{task.status}' 的任务")

        # 2. 查询模型配置
        from app.models.llm_model import LLMModel
        model_result = await db.execute(select(LLMModel).where(LLMModel.id == task.model_id))
        model = model_result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关联的模型不存在")
        from app.utils.crypto import decrypt_api_key
        model_config = {
            "api_base": model.api_base,
            "api_key": decrypt_api_key(model.api_key),
            "model_identifier": model.model_identifier,
        }

        # 3. 查询数据集条目
        items_result = await db.execute(
            select(DatasetItem).where(DatasetItem.dataset_id == task.dataset_id).order_by(DatasetItem.sort_order)
        )
        dataset_items = items_result.scalars().all()
        dataset_items_json = json.dumps([
            {"id": di.id, "input_text": di.input_text, "expected_output": di.expected_output}
            for di in dataset_items
        ], ensure_ascii=False)

        # 4. 查询评测指标
        from app.models.metric import Metric
        metric_ids = [int(mid) for mid in task.metric_ids.split(",") if mid.strip()]
        metric_configs = []
        if metric_ids:
            metric_result = await db.execute(select(Metric).where(Metric.id.in_(metric_ids)))
            metrics = metric_result.scalars().all()
            metric_configs = [
                {"code": m.code, "metric_type": m.metric_type, "config_json": m.config_json, "custom_code": m.custom_code}
                for m in metrics
            ]

        # 5. 清理旧结果（重跑时）并更新状态
        if task.completed_items > 0:
            from sqlalchemy import text
            await db.execute(
                text("DELETE FROM eval_results WHERE eval_task_id = :tid"), {"tid": task_id}
            )
            await db.commit()
        task.status = "running"
        task.total_items = len(dataset_items)
        task.completed_items = 0
        task.overall_score = 0.0
        task.result_json = "{}"
        task.started_at = datetime.utcnow()
        task.error_message = ""
        await db.commit()
        await db.refresh(task)

        # 6. 异步调度 Celery 执行评测
        try:
            from app.tasks.eval_tasks import run_eval_task
            celery_result = run_eval_task.delay(
                task_id=task.id,
                model_config=model_config,
                dataset_items_json=dataset_items_json,
                metric_configs_json=json.dumps(metric_configs),
                prompt_content=task.prompt_content,
            )
            task.celery_task_id = celery_result.id
            await db.commit()
            logger.info("评测任务 %d 已调度, Celery task_id: %s", task.id, celery_result.id)
        except Exception as celery_err:
            # Celery 不可用时回退到同步执行
            logger.warning("Celery 调度失败，回退到直接执行: %s", celery_err)
            from app.tasks.eval_tasks import run_eval_task
            run_eval_task(
                task_id=task.id,
                model_config=model_config,
                dataset_items_json=dataset_items_json,
                metric_configs_json=json.dumps(metric_configs),
                prompt_content=task.prompt_content,
            )

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_EVAL_START, target_type="eval_task",
                        target_id=task_id, detail=f"启动评估任务: {task.name}")

        return EvalTaskResponse(
            id=task.id, name=task.name, project_id=task.project_id,
            model_id=task.model_id, dataset_id=task.dataset_id,
            metric_ids=task.metric_ids, prompt_content=task.prompt_content,
            prompt_id=task.prompt_id, status=task.status,
            schedule_type=task.schedule_type, cron_expression=task.cron_expression,
            total_items=task.total_items, completed_items=task.completed_items,
            overall_score=task.overall_score, error_message=task.error_message,
            started_at=task.started_at, finished_at=task.finished_at,
            created_by=task.created_by, created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("启动评测任务失败")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"启动失败: {str(e)}")


@router.post("/{task_id}/cancel", response_model=EvalTaskResponse)
async def cancel_eval_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_task_executor),
):
    try:
        result = await db.execute(select(EvalTask).where(EvalTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")

        if task.status not in ("pending", "running"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无法取消状态为 '{task.status}' 的任务")

        # 真正取消 Celery 任务
        if task.celery_task_id:
            try:
                from app.tasks.celery_app import celery_app
                celery_app.control.revoke(task.celery_task_id, terminate=True)
                logger.info("已撤销 Celery 任务: %s", task.celery_task_id)
            except Exception as e:
                logger.warning("撤销 Celery 任务失败: %s", e)

        task.status = "cancelled"
        task.finished_at = datetime.utcnow()
        await db.commit()
        await db.refresh(task)

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_EVAL_CANCEL, target_type="eval_task",
                        target_id=task_id, detail=f"取消评估任务: {task.name}")

        return EvalTaskResponse(
            id=task.id,
            name=task.name,
            project_id=task.project_id,
            model_id=task.model_id,
            dataset_id=task.dataset_id,
            metric_ids=task.metric_ids,
            prompt_content=task.prompt_content,
            prompt_id=task.prompt_id,
            status=task.status,
            schedule_type=task.schedule_type,
            cron_expression=task.cron_expression,
            total_items=task.total_items,
            completed_items=task.completed_items,
            overall_score=task.overall_score,
            error_message=task.error_message,
            started_at=task.started_at,
            finished_at=task.finished_at,
            created_by=task.created_by,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_eval_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_task_executor),
):
    try:
        result = await db.execute(select(EvalTask).where(EvalTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")

        # 删除关联的评测结果
        from sqlalchemy import text
        await db.execute(
            text("DELETE FROM eval_results WHERE eval_task_id = :tid"), {"tid": task_id}
        )
        await db.delete(task)
        await db.commit()

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_EVAL_DELETE, target_type="eval_task",
                        target_id=task_id, detail=f"删除评估任务: {task.name}")
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("删除评估任务失败: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"删除失败: {str(e)}")


@router.get("/{task_id}/results", response_model=PaginatedResponse)
async def get_eval_results(
    task_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        task_result = await db.execute(select(EvalTask).where(EvalTask.id == task_id))
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")

        count_result = await db.execute(
            select(func.count(EvalResult.id)).where(EvalResult.eval_task_id == task_id)
        )
        total = count_result.scalar() or 0

        result = await db.execute(
            select(EvalResult)
            .where(EvalResult.eval_task_id == task_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(EvalResult.id)
        )
        results_db = result.scalars().all()

        items = [
            EvalResultResponse(
                id=r.id,
                eval_task_id=r.eval_task_id,
                dataset_item_id=r.dataset_item_id,
                model_output=r.model_output,
                expected_output=r.expected_output,
                scores_json=r.scores_json,
                latency_ms=r.latency_ms,
                error_message=r.error_message,
                created_at=r.created_at,
            )
            for r in results_db
        ]

        total_pages = (total + page_size - 1) // page_size
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except HTTPException:
        raise
    except Exception:
        # Verify the task exists in demo data, else 404
        task_found = False
        for t in DEMO_EVAL_TASKS:
            if t["id"] == task_id:
                task_found = True
                break
        if not task_found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")
        # Return empty results with a note
        return paginated([], 0, page, page_size, 0)


@router.get("/{task_id}/stream")
async def stream_eval_progress(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(EvalTask).where(EvalTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评估任务不存在")

    async def event_generator():
        previous_completed = task.completed_items
        previous_status = task.status

        while True:
            if await request.is_disconnected():
                break

            async with async_session() as session:
                r = await session.execute(select(EvalTask).where(EvalTask.id == task_id))
                current_task = r.scalar_one_or_none()

                if not current_task:
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": "Task not found"}),
                    }
                    break

                changed = (
                    current_task.completed_items != previous_completed
                    or current_task.status != previous_status
                )
                if changed:
                    progress = (
                        current_task.completed_items / max(current_task.total_items, 1) * 100
                    )
                    event_data = {
                        "task_id": current_task.id,
                        "status": current_task.status,
                        "completed_items": current_task.completed_items,
                        "total_items": current_task.total_items,
                        "progress": round(progress, 2),
                        "overall_score": current_task.overall_score,
                    }
                    yield {
                        "event": "progress",
                        "data": json.dumps(event_data),
                    }
                    previous_completed = current_task.completed_items
                    previous_status = current_task.status

                if current_task.status in ("completed", "failed", "cancelled"):
                    final_data = {
                        "task_id": current_task.id,
                        "status": current_task.status,
                        "completed_items": current_task.completed_items,
                        "total_items": current_task.total_items,
                        "overall_score": current_task.overall_score,
                        "error_message": current_task.error_message,
                    }
                    yield {
                        "event": "complete",
                        "data": json.dumps(final_data),
                    }
                    break

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
