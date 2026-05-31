import json
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.dataset import Dataset
from app.models.eval_task import EvalTask
from app.models.prompt import Prompt
from app.models.optimization import OptimizationTask
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDashboard
from app.schemas.common import PaginatedResponse
from .demo_data import DEMO_PROJECTS, get_demo_list, paginated

router = APIRouter(tags=["projects"])


@router.get("/", response_model=PaginatedResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    project_type: str = Query(None, description="Filter by project type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = select(Project)
        count_query = select(func.count(Project.id))

        if project_type:
            query = query.where(Project.project_type == project_type)
            count_query = count_query.where(Project.project_type == project_type)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        result = await db.execute(
            query.offset((page - 1) * page_size).limit(page_size).order_by(Project.id.desc())
        )
        projects = result.scalars().all()

        items = [
            ProjectResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                project_type=p.project_type,
                status=p.status,
                created_by=p.created_by,
                created_at=p.created_at,
            )
            for p in projects
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
        items, total, _, _, total_pages = get_demo_list(DEMO_PROJECTS, page, page_size)
        return paginated([ProjectResponse(**item) for item in items], total, page, page_size, total_pages)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            project_type=project.project_type,
            status=project.status,
            created_by=project.created_by,
            created_at=project.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        for proj in DEMO_PROJECTS:
            if proj["id"] == project_id:
                return ProjectResponse(**proj)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = Project(
            name=req.name,
            description=req.description or "",
            project_type=req.project_type or "chat",
            created_by=current_user.id,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)

        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            project_type=project.project_type,
            status=project.status,
            created_by=project.created_by,
            created_at=project.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    req: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(project, key, value)

        await db.commit()
        await db.refresh(project)

        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            project_type=project.project_type,
            status=project.status,
            created_by=project.created_by,
            created_at=project.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

        await db.delete(project)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.get("/{project_id}/dashboard", response_model=ProjectDashboard)
async def get_project_dashboard(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

        # Count datasets
        dataset_count_result = await db.execute(
            select(func.count(Dataset.id))
        )
        dataset_count = dataset_count_result.scalar() or 0

        # Count eval tasks
        eval_total_result = await db.execute(
            select(func.count(EvalTask.id)).where(EvalTask.project_id == project_id)
        )
        eval_total = eval_total_result.scalar() or 0

        eval_running_result = await db.execute(
            select(func.count(EvalTask.id)).where(
                EvalTask.project_id == project_id, EvalTask.status == "running"
            )
        )
        eval_running = eval_running_result.scalar() or 0

        eval_completed_result = await db.execute(
            select(func.count(EvalTask.id)).where(
                EvalTask.project_id == project_id, EvalTask.status == "completed"
            )
        )
        eval_completed = eval_completed_result.scalar() or 0

        eval_failed_result = await db.execute(
            select(func.count(EvalTask.id)).where(
                EvalTask.project_id == project_id, EvalTask.status == "failed"
            )
        )
        eval_failed = eval_failed_result.scalar() or 0

        # Average score from completed evals
        avg_score_result = await db.execute(
            select(func.avg(EvalTask.overall_score)).where(
                EvalTask.project_id == project_id, EvalTask.status == "completed"
            )
        )
        avg_score = avg_score_result.scalar() or 0.0

        # Count prompts
        prompt_count_result = await db.execute(
            select(func.count(Prompt.id)).where(Prompt.project_id == project_id)
        )
        prompt_count = prompt_count_result.scalar() or 0

        # Best prompt score
        best_prompt_result = await db.execute(
            select(func.max(Prompt.best_score)).where(Prompt.project_id == project_id)
        )
        best_prompt_score = best_prompt_result.scalar() or 0.0

        # Count optimization tasks
        opt_count_result = await db.execute(
            select(func.count(OptimizationTask.id)).where(OptimizationTask.project_id == project_id)
        )
        opt_count = opt_count_result.scalar() or 0

        # Latest eval scores
        latest_evals_result = await db.execute(
            select(EvalTask)
            .where(EvalTask.project_id == project_id, EvalTask.status == "completed")
            .order_by(EvalTask.finished_at.desc().nullslast())
            .limit(5)
        )
        latest_evals = latest_evals_result.scalars().all()

        latest_eval_scores = json.dumps([
            {"task_id": e.id, "name": e.name, "score": e.overall_score}
            for e in latest_evals
        ])

        project_resp = ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            project_type=project.project_type,
            status=project.status,
            created_by=project.created_by,
            created_at=project.created_at,
        )

        return ProjectDashboard(
            project=project_resp,
            dataset_count=dataset_count,
            eval_task_count=eval_total,
            optimization_task_count=opt_count,
            best_prompt_score=best_prompt_score,
            latest_eval_scores=latest_eval_scores,
        )
    except HTTPException:
        raise
    except Exception:
        proj = None
        for p in DEMO_PROJECTS:
            if p["id"] == project_id:
                proj = p
                break
        if not proj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

        project_resp = ProjectResponse(**proj)
        return ProjectDashboard(
            project=project_resp,
            dataset_count=2,
            eval_task_count=2,
            optimization_task_count=1,
            best_prompt_score=0.86,
            latest_eval_scores=json.dumps([
                {"task_id": 1, "name": "金融QA-初始Prompt评测", "score": 0.32},
                {"task_id": 2, "name": "金融QA-优化后评测", "score": 0.86},
            ]),
        )
