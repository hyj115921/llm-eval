"""
Celery 异步评测任务
"""
import json
import asyncio
from datetime import datetime

from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, track_started=True)
def run_eval_task(self, task_id: int, model_config: dict, dataset_items_json: str,
                  metric_configs_json: str, prompt_content: str):
    """
    异步执行评测任务。
    注意：Celery 是同步的，需要在内部运行 asyncio loop。
    """
    from app.services.llm_service import llm_service
    from app.services.evaluator import evaluator
    from sqlalchemy import select, update
    from app.core.database import async_session
    from app.models.eval_task import EvalTask, EvalResult

    dataset_items = json.loads(dataset_items_json)
    metric_configs = json.loads(metric_configs_json)

    async def _run():
        async with async_session() as db:
            # 更新状态为运行中
            await db.execute(
                update(EvalTask).where(EvalTask.id == task_id).values(
                    status="running",
                    total_items=len(dataset_items),
                    started_at=datetime.utcnow(),
                )
            )
            await db.commit()

        total_score = 0.0
        completed = 0
        metric_count = len(metric_configs) if metric_configs else 1
        sem = asyncio.Semaphore(5)

        async def process_item(idx: int, item: dict):
            nonlocal total_score, completed
            async with sem:
                from app.services.llm_service import build_messages
                messages = build_messages(prompt_content, item["input_text"])
                llm_result = await llm_service.chat(
                    api_base=model_config["api_base"],
                    api_key=model_config["api_key"],
                    model_identifier=model_config["model_identifier"],
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1024,
                )

                model_output = llm_result.get("content", "")
                latency_ms = llm_result.get("latency_ms", 0)
                error_msg = llm_result.get("error", "") if not llm_result["success"] else ""

                scores = await evaluator.evaluate_single(
                    model_output=model_output,
                    expected_output=item.get("expected_output", ""),
                    metric_configs=metric_configs,
                    judge_model_config=None,
                )

                item_avg = sum(s.get("score", 0) for s in scores.values()) / max(metric_count, 1)

                async with async_session() as db:
                    # 保存逐条结果
                    result = EvalResult(
                        eval_task_id=task_id,
                        dataset_item_id=item.get("id", idx),
                        model_output=model_output,
                        expected_output=item.get("expected_output", ""),
                        scores_json=json.dumps(scores, ensure_ascii=False),
                        latency_ms=latency_ms,
                        error_message=error_msg,
                    )
                    db.add(result)
                    await db.commit()

                total_score += item_avg
                completed += 1

                # 更新进度
                async with async_session() as db:
                    await db.execute(
                        update(EvalTask).where(EvalTask.id == task_id).values(
                            completed_items=completed,
                        )
                    )
                    await db.commit()

                # 更新 Celery 进度
                self.update_state(state="PROGRESS", meta={"completed": completed, "total": len(dataset_items)})

        # 并发处理所有样本
        tasks = [process_item(i, item) for i, item in enumerate(dataset_items)]
        await asyncio.gather(*tasks)

        # 计算最终得分
        final_score = total_score / len(dataset_items) if dataset_items else 0.0
        result_json = json.dumps({
            "overall_score": final_score,
            "total_items": len(dataset_items),
            "metric_count": metric_count,
        }, ensure_ascii=False)

        async with async_session() as db:
            await db.execute(
                update(EvalTask).where(EvalTask.id == task_id).values(
                    status="completed",
                    overall_score=round(final_score, 4),
                    completed_items=len(dataset_items),
                    result_json=result_json,
                    finished_at=datetime.utcnow(),
                )
            )
            await db.commit()

        return {"status": "completed", "score": final_score}

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception as e:
        # 处理失败
        async def _fail():
            async with async_session() as db:
                await db.execute(
                    update(EvalTask).where(EvalTask.id == task_id).values(
                        status="failed",
                        error_message=str(e),
                        finished_at=datetime.utcnow(),
                    )
                )
                await db.commit()

        loop = asyncio.new_event_loop()
        loop.run_until_complete(_fail())
        loop.close()
        raise
