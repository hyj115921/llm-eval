"""
定时任务调度器 — 每分钟扫描待执行的定时评测任务并触发执行。
配合 Celery Beat 使用，在 celery_app.py 中注册为 periodic task。
"""
import json
import logging
from datetime import datetime

from croniter import croniter
from sqlalchemy import select, update

from app.tasks.celery_app import celery_app
from app.core.database import async_session
from app.models.eval_task import EvalTask
from app.models.llm_model import LLMModel
from app.models.dataset import DatasetItem
from app.models.metric import Metric

logger = logging.getLogger(__name__)


@celery_app.task(name="scheduler.scan_scheduled_tasks")
def scan_scheduled_tasks():
    """
    每分钟执行一次，扫描所有 status='pending' 且 schedule_type='scheduled' 的任务，
    如果 cron expression 匹配当前时间，则触发执行。
    """
    import asyncio

    async def _scan():
        async with async_session() as db:
            result = await db.execute(
                select(EvalTask).where(
                    EvalTask.schedule_type == "scheduled",
                    EvalTask.status == "pending",
                )
            )
            tasks = result.scalars().all()

            now = datetime.utcnow()
            triggered = 0

            for task in tasks:
                if not task.cron_expression:
                    continue

                try:
                    cron = croniter(task.cron_expression, task.created_at or now)
                    prev_time = cron.get_prev(datetime)

                    # 检查是否在最近 2 分钟内应该触发
                    delta = (now - prev_time).total_seconds()
                    if 0 <= delta <= 120:
                        # 触发执行
                        await _trigger_eval_task(db, task)
                        triggered += 1
                        logger.info("定时触发评测任务 %d: %s (cron: %s)", task.id, task.name, task.cron_expression)
                except Exception as e:
                    logger.warning("解析 cron 表达式失败 (task %d): %s", task.id, e)

            if triggered > 0:
                logger.info("本轮触发 %d 个定时任务", triggered)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_scan())
    finally:
        loop.close()


async def _trigger_eval_task(db, task: EvalTask):
    """触发单个评测任务执行"""
    from app.tasks.eval_tasks import run_eval_task
    from app.utils.crypto import decrypt_api_key

    # 查询模型配置
    model_result = await db.execute(select(LLMModel).where(LLMModel.id == task.model_id))
    model = model_result.scalar_one_or_none()
    if not model:
        logger.error("定时任务 %d: 模型 %d 不存在", task.id, task.model_id)
        await db.execute(update(EvalTask).where(EvalTask.id == task.id).values(
            status="failed", error_message=f"模型 {task.model_id} 不存在"
        ))
        await db.commit()
        return

    model_config = {
        "api_base": model.api_base,
        "api_key": decrypt_api_key(model.api_key),
        "model_identifier": model.model_identifier,
    }

    # 查询数据集
    items_result = await db.execute(
        select(DatasetItem).where(DatasetItem.dataset_id == task.dataset_id).order_by(DatasetItem.sort_order)
    )
    dataset_items = items_result.scalars().all()
    dataset_items_json = json.dumps([
        {"id": di.id, "input_text": di.input_text, "expected_output": di.expected_output}
        for di in dataset_items
    ], ensure_ascii=False)

    # 查询指标
    metric_ids = [int(mid) for mid in task.metric_ids.split(",") if mid.strip()]
    metric_configs = []
    if metric_ids:
        metric_result = await db.execute(select(Metric).where(Metric.id.in_(metric_ids)))
        metrics = metric_result.scalars().all()
        metric_configs = [
            {"code": m.code, "metric_type": m.metric_type, "config_json": m.config_json, "custom_code": m.custom_code}
            for m in metrics
        ]

    # 更新状态
    await db.execute(update(EvalTask).where(EvalTask.id == task.id).values(
        status="running",
        total_items=len(dataset_items),
        started_at=datetime.utcnow(),
        error_message="",
    ))
    await db.commit()

    # 调度 Celery 执行
    try:
        celery_result = run_eval_task.delay(
            task_id=task.id,
            model_config=model_config,
            dataset_items_json=dataset_items_json,
            metric_configs_json=json.dumps(metric_configs),
            prompt_content=task.prompt_content,
        )
        await db.execute(update(EvalTask).where(EvalTask.id == task.id).values(
            celery_task_id=celery_result.id,
        ))
        await db.commit()
    except Exception as e:
        logger.exception("定时任务 %d Celery 调度失败", task.id)
        await db.execute(update(EvalTask).where(EvalTask.id == task.id).values(
            status="failed", error_message=str(e)
        ))
        await db.commit()
