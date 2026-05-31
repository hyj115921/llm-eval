import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.prompt import Prompt, PromptVersion
from app.models.optimization import OptimizationTask, OptimizationRound
from app.schemas.prompt import (
    PromptCreate,
    PromptUpdate,
    PromptResponse,
    PromptVersionResponse,
    OptimizationTaskCreate,
    OptimizationTaskResponse,
    OptimizationRoundResponse,
)
from app.schemas.common import PaginatedResponse
from .demo_data import DEMO_PROMPTS, DEMO_OPT_TASKS, get_demo_list, paginated
from app.utils.audit import audit_log, ACTION_OPTIMIZATION_CREATE, \
    ACTION_OPTIMIZATION_START, ACTION_OPTIMIZATION_CANCEL

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prompts"])


# ─── Prompt CRUD ────────────────────────────────────────────────────────────


@router.get("/", response_model=PaginatedResponse)
async def list_prompts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        count_result = await db.execute(select(func.count(Prompt.id)))
        total = count_result.scalar() or 0

        result = await db.execute(
            select(Prompt).offset((page - 1) * page_size).limit(page_size).order_by(Prompt.id.desc())
        )
        prompts = result.scalars().all()

        items = [
            PromptResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                scene=p.scene,
                current_version=p.current_version,
                current_content=p.current_content,
                best_score=p.best_score,
                project_id=p.project_id,
                created_by=p.created_by,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in prompts
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
        items, total, _, _, total_pages = get_demo_list(DEMO_PROMPTS, page, page_size)
        return paginated([PromptResponse(**item) for item in items], total, page, page_size, total_pages)


@router.get("/{prompt_id:int}", response_model=PromptResponse)
async def get_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt不存在")

        return PromptResponse(
            id=prompt.id,
            name=prompt.name,
            description=prompt.description,
            scene=prompt.scene,
            current_version=prompt.current_version,
            current_content=prompt.current_content,
            best_score=prompt.best_score,
            project_id=prompt.project_id,
            created_by=prompt.created_by,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        for prompt in DEMO_PROMPTS:
            if prompt["id"] == prompt_id:
                return PromptResponse(**prompt)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt不存在")


@router.post("/", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    req: PromptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prompt = Prompt(
            name=req.name,
            description=req.description or "",
            scene=req.scene or "general",
            current_content=req.content or "",
            current_version="v1",
            created_by=current_user.id,
            project_id=req.project_id,
        )
        db.add(prompt)
        await db.flush()

        # Create initial version record
        version = PromptVersion(
            prompt_id=prompt.id,
            version="v1",
            content=req.content or "",
            score=0.0,
            source="initial",
        )
        db.add(version)
        await db.commit()
        await db.refresh(prompt)

        return PromptResponse(
            id=prompt.id,
            name=prompt.name,
            description=prompt.description,
            scene=prompt.scene,
            current_version=prompt.current_version,
            current_content=prompt.current_content,
            best_score=prompt.best_score,
            project_id=prompt.project_id,
            created_by=prompt.created_by,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: int,
    req: PromptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt不存在")

        # If content changed, create a new version
        if req.content is not None and req.content != prompt.current_content:
            # Determine next version number
            version_result = await db.execute(
                select(func.count(PromptVersion.id)).where(PromptVersion.prompt_id == prompt_id)
            )
            version_count = version_result.scalar() or 0
            new_version = f"v{version_count + 1}"

            new_pv = PromptVersion(
                prompt_id=prompt_id,
                version=new_version,
                content=req.content,
                score=0.0,
                source="manual",
            )
            db.add(new_pv)
            prompt.current_version = new_version
            prompt.current_content = req.content

        # Apply other updates
        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key != "content":  # already handled
                setattr(prompt, key, value)

        await db.commit()
        await db.refresh(prompt)

        return PromptResponse(
            id=prompt.id,
            name=prompt.name,
            description=prompt.description,
            scene=prompt.scene,
            current_version=prompt.current_version,
            current_content=prompt.current_content,
            best_score=prompt.best_score,
            project_id=prompt.project_id,
            created_by=prompt.created_by,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt不存在")

        await db.delete(prompt)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.get("/{prompt_id:int}/versions", response_model=PaginatedResponse)
async def list_prompt_versions(
    prompt_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        prompt_result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
        prompt = prompt_result.scalar_one_or_none()
        if not prompt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt不存在")

        count_result = await db.execute(
            select(func.count(PromptVersion.id)).where(PromptVersion.prompt_id == prompt_id)
        )
        total = count_result.scalar() or 0

        result = await db.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(PromptVersion.id.desc())
        )
        versions = result.scalars().all()

        items = [
            PromptVersionResponse(
                id=v.id,
                prompt_id=v.prompt_id,
                version=v.version,
                content=v.content,
                score=v.score,
                source=v.source,
                optimization_task_id=v.optimization_task_id,
                created_at=v.created_at,
            )
            for v in versions
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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


# ─── Optimization Tasks ─────────────────────────────────────────────────────


@router.get("/optimization", response_model=PaginatedResponse)
async def list_optimization_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = select(OptimizationTask)
        count_query = select(func.count(OptimizationTask.id))
        if status:
            query = query.where(OptimizationTask.status == status)
            count_query = count_query.where(OptimizationTask.status == status)
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        result = await db.execute(
            query.offset((page - 1) * page_size).limit(page_size).order_by(OptimizationTask.id.desc())
        )
        tasks = result.scalars().all()
        items = [
            OptimizationTaskResponse(
                id=t.id, name=t.name, project_id=t.project_id,
                model_id=t.model_id, optimizer_model_id=t.optimizer_model_id,
                dataset_id=t.dataset_id, initial_prompt=t.initial_prompt,
                best_prompt=t.best_prompt, best_score=t.best_score,
                baseline_score=t.baseline_score, max_rounds=t.max_rounds,
                current_round=t.current_round, status=t.status,
                score_history_json=t.score_history_json,
                started_at=t.started_at, finished_at=t.finished_at,
                created_at=t.created_at,
            )
            for t in tasks
        ]
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        return PaginatedResponse(
            items=items, total=total, page=page, page_size=page_size, total_pages=total_pages,
        )
    except HTTPException:
        raise
    except Exception:
        items, total, _, _, total_pages = get_demo_list(DEMO_OPT_TASKS, page, page_size)
        return paginated([OptimizationTaskResponse(**item) for item in items], total, page, page_size, total_pages)


@router.post("/optimization", response_model=OptimizationTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_optimization_task(
    req: OptimizationTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 校验数据集已发布
        from app.models.dataset import Dataset
        ds_result = await db.execute(select(Dataset).where(Dataset.id == req.dataset_id))
        dataset = ds_result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
        if dataset.status not in ("approved", "published"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"数据集状态为 '{dataset.status}'，只有已审核/已发布的数据集才能用于优化")

        # 校验指标均已审核
        from app.models.metric import Metric
        m_ids = [int(mid) for mid in (req.metric_ids or "").split(",") if mid.strip()]
        if m_ids:
            m_result = await db.execute(select(Metric).where(Metric.id.in_(m_ids)))
            for m in m_result.scalars().all():
                if m.status != "approved":
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"评测标准 '{m.name}' 状态为 '{m.status}'，只有已审核的标准才能用于优化")

        # 应用优化策略预设
        from app.schemas.prompt import OPTIMIZATION_STRATEGIES
        strategy_config = OPTIMIZATION_STRATEGIES.get(req.strategy, OPTIMIZATION_STRATEGIES["balanced"])
        max_rounds = req.max_rounds if req.max_rounds > 0 else strategy_config["max_rounds"]
        candidates = req.candidates_per_round if req.candidates_per_round > 0 else strategy_config["candidates_per_round"]
        threshold = req.convergence_threshold if req.convergence_threshold > 0 else strategy_config["convergence_threshold"]

        task = OptimizationTask(
            name=req.name,
            project_id=req.project_id,
            prompt_id=req.prompt_id,
            model_id=req.model_id,
            optimizer_model_id=req.optimizer_model_id,
            dataset_id=req.dataset_id,
            metric_ids=req.metric_ids or "",
            initial_prompt=req.initial_prompt or "",
            max_rounds=max_rounds,
            candidates_per_round=candidates,
            convergence_threshold=threshold,
            created_by=current_user.id,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_OPTIMIZATION_CREATE, target_type="optimization_task",
                        target_id=task.id, detail=f"创建优化任务: {task.name}")

        return OptimizationTaskResponse(
            id=task.id,
            name=task.name,
            project_id=task.project_id,
            model_id=task.model_id,
            optimizer_model_id=task.optimizer_model_id,
            dataset_id=task.dataset_id,
            initial_prompt=task.initial_prompt,
            best_prompt=task.best_prompt,
            best_score=task.best_score,
            baseline_score=task.baseline_score,
            max_rounds=task.max_rounds,
            current_round=task.current_round,
            status=task.status,
            score_history_json=task.score_history_json,
            started_at=task.started_at,
            finished_at=task.finished_at,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.get("/optimization/{task_id}", response_model=OptimizationTaskResponse)
async def get_optimization_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(OptimizationTask).where(OptimizationTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")

        return OptimizationTaskResponse(
            id=task.id,
            name=task.name,
            project_id=task.project_id,
            model_id=task.model_id,
            optimizer_model_id=task.optimizer_model_id,
            dataset_id=task.dataset_id,
            initial_prompt=task.initial_prompt,
            best_prompt=task.best_prompt,
            best_score=task.best_score,
            baseline_score=task.baseline_score,
            max_rounds=task.max_rounds,
            current_round=task.current_round,
            status=task.status,
            score_history_json=task.score_history_json,
            started_at=task.started_at,
            finished_at=task.finished_at,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        for task in DEMO_OPT_TASKS:
            if task["id"] == task_id:
                return OptimizationTaskResponse(**task)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")


@router.post("/optimization/{task_id}/start", response_model=OptimizationTaskResponse)
async def start_optimization(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 1. 查询优化任务
        result = await db.execute(select(OptimizationTask).where(OptimizationTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")

        if task.status not in ("pending", "failed"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无法启动状态为 '{task.status}' 的任务")

        # 2. 查询模型配置
        from app.models.llm_model import LLMModel
        model_result = await db.execute(select(LLMModel).where(LLMModel.id == task.model_id))
        model = model_result.scalar_one_or_none()
        optimizer_result = await db.execute(select(LLMModel).where(LLMModel.id == task.optimizer_model_id))
        optimizer_model = optimizer_result.scalar_one_or_none()
        if not model or not optimizer_model:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="关联的模型不存在")

        # 3. 查询数据集条目
        from app.models.dataset import DatasetItem as DIDataItem
        items_result = await db.execute(
            select(DIDataItem).where(DIDataItem.dataset_id == task.dataset_id).order_by(DIDataItem.sort_order)
        )
        dataset_items = items_result.scalars().all()
        dataset_items_json = json.dumps([
            {"id": di.id, "input_text": di.input_text, "expected_output": di.expected_output}
            for di in dataset_items
        ], ensure_ascii=False)

        # 4. 查询指标
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

        # 5. 构建配置
        config_data = {
            "model_config": {"api_base": model.api_base, "api_key": model.api_key, "model_identifier": model.model_identifier},
            "optimizer_model_config": {"api_base": optimizer_model.api_base, "api_key": optimizer_model.api_key, "model_identifier": optimizer_model.model_identifier},
            "metric_configs": metric_configs,
            "initial_prompt": task.initial_prompt,
            "max_rounds": task.max_rounds,
            "candidates_per_round": task.candidates_per_round,
            "convergence_threshold": task.convergence_threshold,
            "prompt_id": task.prompt_id,
        }

        # 6. 更新状态
        task.status = "running"
        task.started_at = datetime.utcnow()
        task.error_message = ""
        await db.commit()
        await db.refresh(task)

        # 7. 异步调度 Celery
        try:
            from app.tasks.optimization_tasks import run_optimization_task
            celery_result = run_optimization_task.delay(
                task_id=task.id,
                config_json=json.dumps(config_data),
                dataset_items_json=dataset_items_json,
            )
            task.celery_task_id = celery_result.id
            await db.commit()
            logger.info("优化任务 %d 已调度, Celery task_id: %s", task.id, celery_result.id)
        except Exception as celery_err:
            logger.warning("Celery 调度失败: %s，回退到同步执行", celery_err)
            from app.tasks.optimization_tasks import run_optimization_task
            run_optimization_task(
                task_id=task.id,
                config_json=json.dumps(config_data),
                dataset_items_json=dataset_items_json,
            )

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_OPTIMIZATION_START, target_type="optimization_task",
                        target_id=task_id, detail=f"启动优化任务: {task.name}")

        return OptimizationTaskResponse(
            id=task.id, name=task.name, project_id=task.project_id,
            model_id=task.model_id, optimizer_model_id=task.optimizer_model_id,
            dataset_id=task.dataset_id, initial_prompt=task.initial_prompt,
            best_prompt=task.best_prompt, best_score=task.best_score,
            baseline_score=task.baseline_score, max_rounds=task.max_rounds,
            current_round=task.current_round, status=task.status,
            score_history_json=task.score_history_json,
            started_at=task.started_at, finished_at=task.finished_at,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("启动优化任务失败")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"启动失败: {str(e)}")


@router.post("/optimization/{task_id}/cancel", response_model=OptimizationTaskResponse)
async def cancel_optimization(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(OptimizationTask).where(OptimizationTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")

        if task.status not in ("pending", "running"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无法取消状态为 '{task.status}' 的任务")

        task.status = "cancelled"
        task.finished_at = datetime.utcnow()
        await db.commit()
        await db.refresh(task)

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_OPTIMIZATION_CANCEL, target_type="optimization_task",
                        target_id=task_id, detail=f"取消优化任务: {task.name}")

        return OptimizationTaskResponse(
            id=task.id,
            name=task.name,
            project_id=task.project_id,
            model_id=task.model_id,
            optimizer_model_id=task.optimizer_model_id,
            dataset_id=task.dataset_id,
            initial_prompt=task.initial_prompt,
            best_prompt=task.best_prompt,
            best_score=task.best_score,
            baseline_score=task.baseline_score,
            max_rounds=task.max_rounds,
            current_round=task.current_round,
            status=task.status,
            score_history_json=task.score_history_json,
            started_at=task.started_at,
            finished_at=task.finished_at,
            created_at=task.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.get("/optimization/{task_id}/rounds", response_model=PaginatedResponse)
async def list_optimization_rounds(
    task_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        task_result = await db.execute(select(OptimizationTask).where(OptimizationTask.id == task_id))
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")

        count_result = await db.execute(
            select(func.count(OptimizationRound.id)).where(
                OptimizationRound.optimization_task_id == task_id
            )
        )
        total = count_result.scalar() or 0

        result = await db.execute(
            select(OptimizationRound)
            .where(OptimizationRound.optimization_task_id == task_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(OptimizationRound.round_number.asc())
        )
        rounds = result.scalars().all()

        items = [
            OptimizationRoundResponse(
                id=r.id,
                optimization_task_id=r.optimization_task_id,
                round_number=r.round_number,
                prompt_before=r.prompt_before,
                best_prompt_after=r.best_prompt_after,
                score_before=r.score_before,
                score_after=r.score_after,
                candidates_json=r.candidates_json,
                error_samples_json=r.error_samples_json,
                created_at=r.created_at,
            )
            for r in rounds
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
        # Verify the optimization task exists in demo data
        task_found = False
        for t in DEMO_OPT_TASKS:
            if t["id"] == task_id:
                task_found = True
                break
        if not task_found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="优化任务不存在")
        # Return empty rounds for demo mode
        return paginated([], 0, page, page_size, 0)
