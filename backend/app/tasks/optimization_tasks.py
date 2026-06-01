"""
Celery 异步 Prompt 优化任务
"""
import json
import asyncio
from datetime import datetime

from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, track_started=True)
def run_optimization_task(self, task_id: int, config_json: str, dataset_items_json: str):
    """
    异步执行 Prompt 优化任务
    """
    from app.services.optimizer import optimizer, OptimizationConfig
    from sqlalchemy import select, update
    from app.core.database import async_session
    from app.models.optimization import OptimizationTask, OptimizationRound, OptimizationCandidate
    from app.models.prompt import Prompt, PromptVersion

    config_data = json.loads(config_json)
    dataset_items = json.loads(dataset_items_json)

    opt_config = OptimizationConfig(
        model_config=config_data["model_config"],
        optimizer_model_config=config_data["optimizer_model_config"],
        metric_configs=config_data["metric_configs"],
        max_rounds=config_data.get("max_rounds", 10),
        candidates_per_round=config_data.get("candidates_per_round", 3),
        convergence_threshold=config_data.get("convergence_threshold", 0.01),
    )

    async def progress_callback(round_num, best_score, best_prompt, status):
        async with async_session() as db:
            await db.execute(
                update(OptimizationTask).where(OptimizationTask.id == task_id).values(
                    current_round=round_num,
                    best_score=round(best_score, 4),
                    best_prompt=best_prompt,
                    score_history_json=json.dumps(score_history_tracker, ensure_ascii=False),
                )
            )
            await db.commit()
        self.update_state(state="PROGRESS", meta={
            "round": round_num, "score": best_score, "status": status
        })

    score_history_tracker = []
    prompt_history_tracker = [config_data["initial_prompt"]]

    async def _run():
        nonlocal score_history_tracker

        from app.core.database import engine
        await engine.dispose()

        async with async_session() as db:
            # 更新状态
            await db.execute(
                update(OptimizationTask).where(OptimizationTask.id == task_id).values(
                    status="running",
                    started_at=datetime.utcnow(),
                )
            )
            await db.commit()

        # 包装 progress_callback 以记录分数历史和保存轮次详情
        async def wrapped_progress(round_num, best_score, best_prompt, status):
            nonlocal score_history_tracker
            score_history_tracker.append(best_score)
            await progress_callback(round_num, best_score, best_prompt, status)
            # 每轮完成后立即保存轮次记录，前端能看到实时更新的轮次表
            if round_num > 0:
                prev_score = score_history_tracker[-2] if len(score_history_tracker) > 1 else 0.0
                prev_prompt = prompt_history_tracker[-1] if prompt_history_tracker else ""
                prompt_history_tracker.append(best_prompt)
                async with async_session() as db2:
                    existing = await db2.execute(
                        select(OptimizationRound).where(
                            OptimizationRound.optimization_task_id == task_id,
                            OptimizationRound.round_number == round_num,
                        )
                    )
                    if not existing.scalar_one_or_none():
                        db2.add(OptimizationRound(
                            optimization_task_id=task_id,
                            round_number=round_num,
                            prompt_before=prev_prompt,
                            best_prompt_after=best_prompt,
                            score_before=round(prev_score, 4),
                            score_after=round(best_score, 4),
                            candidates_json="[]",
                            error_samples_json="[]",
                        ))
                        await db2.commit()

        result = await optimizer.optimize(
            task_id=task_id,
            config=opt_config,
            dataset_items=dataset_items,
            initial_prompt=config_data["initial_prompt"],
            progress_callback=wrapped_progress,
        )

        # 保存详细结果到数据库
        async with async_session() as db:
            await db.execute(
                update(OptimizationTask).where(OptimizationTask.id == task_id).values(
                    status=result["status"],
                    best_prompt=result["best_prompt"],
                    best_score=round(result["best_score"], 4),
                    baseline_score=round(result["baseline_score"], 4),
                    current_round=len(result["rounds"]),
                    score_history_json=json.dumps(result["score_history"], ensure_ascii=False),
                    finished_at=datetime.utcnow(),
                )
            )
            await db.commit()

            # 更新每轮详情（candidates/error_samples 等完整数据）
            for rd in result["rounds"]:
                await db.execute(
                    update(OptimizationRound).where(
                        OptimizationRound.optimization_task_id == task_id,
                        OptimizationRound.round_number == rd["round_number"],
                    ).values(
                        prompt_before=rd["prompt_before"],
                        best_prompt_after=rd["best_prompt_after"],
                        score_before=rd["score_before"],
                        score_after=rd["score_after"],
                        candidates_json=json.dumps(rd["candidates"], ensure_ascii=False),
                        error_samples_json=json.dumps(rd["error_samples"], ensure_ascii=False),
                    )
                )
            await db.commit()

            # 更新关联的 Prompt 记录
            prompt_id = config_data.get("prompt_id")
            if prompt_id:
                await db.execute(
                    update(Prompt).where(Prompt.id == prompt_id).values(
                        current_content=result["best_prompt"],
                        best_score=round(result["best_score"], 4),
                        current_version=f"v{len(result['rounds']) + 1}",
                    )
                )
                await db.commit()

                # 创建新版本记录
                version = PromptVersion(
                    prompt_id=prompt_id,
                    version=f"v{len(result['rounds']) + 1}",
                    content=result["best_prompt"],
                    score=round(result["best_score"], 4),
                    source="optimization",
                    optimization_task_id=task_id,
                )
                db.add(version)
                await db.commit()

        return {"status": result["status"], "best_score": result["best_score"]}

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        output = loop.run_until_complete(_run())
        loop.close()
        return output
    except Exception as e:
        async def _fail():
            from app.core.database import engine
            await engine.dispose()
            async with async_session() as db:
                await db.execute(
                    update(OptimizationTask).where(OptimizationTask.id == task_id).values(
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
