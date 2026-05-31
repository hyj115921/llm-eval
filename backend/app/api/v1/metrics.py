from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user, require_data_manager, require_approver
from app.models.user import User
from app.models.metric import Metric
from app.schemas.metric import MetricCreate, MetricUpdate, MetricResponse
from app.schemas.dataset import DatasetReview
from app.schemas.common import PaginatedResponse

router = APIRouter(tags=["metrics"])


@router.get("/", response_model=PaginatedResponse)
async def list_metrics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count_result = await db.execute(select(func.count(Metric.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Metric).offset((page - 1) * page_size).limit(page_size).order_by(Metric.id)
    )
    metrics = result.scalars().all()

    items = [
        MetricResponse(
            id=m.id,
            name=m.name,
            code=m.code,
            description=m.description,
            metric_type=m.metric_type,
            config_json=m.config_json,
            status=m.status,
            is_active=m.is_active,
            created_by=m.created_by,
            created_at=m.created_at,
        )
        for m in metrics
    ]

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{metric_id}", response_model=MetricResponse)
async def get_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Metric).where(Metric.id == metric_id))
    metric = result.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")

    return MetricResponse(
        id=metric.id,
        name=metric.name,
        code=metric.code,
        description=metric.description,
        metric_type=metric.metric_type,
        config_json=metric.config_json,
        status=metric.status,
        is_active=metric.is_active,
        created_by=metric.created_by,
        created_at=metric.created_at,
    )


@router.post("/", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
async def create_metric(
    req: MetricCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    existing_result = await db.execute(select(Metric).where(Metric.code == req.code))
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="指标代码已存在")

    metric = Metric(
        name=req.name,
        code=req.code,
        description=req.description or "",
        metric_type=req.metric_type or "builtin",
        config_json=req.config_json or "{}",
        custom_code=req.custom_code or "",
        created_by=current_user.id,
    )
    db.add(metric)
    await db.commit()
    await db.refresh(metric)

    return MetricResponse(
        id=metric.id,
        name=metric.name,
        code=metric.code,
        description=metric.description,
        metric_type=metric.metric_type,
        config_json=metric.config_json,
        status=metric.status,
        is_active=metric.is_active,
        created_by=metric.created_by,
        created_at=metric.created_at,
    )


@router.put("/{metric_id}", response_model=MetricResponse)
async def update_metric(
    metric_id: int,
    req: MetricUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    result = await db.execute(select(Metric).where(Metric.id == metric_id))
    metric = result.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(metric, key, value)

    await db.commit()
    await db.refresh(metric)

    return MetricResponse(
        id=metric.id,
        name=metric.name,
        code=metric.code,
        description=metric.description,
        metric_type=metric.metric_type,
        config_json=metric.config_json,
        status=metric.status,
        is_active=metric.is_active,
        created_by=metric.created_by,
        created_at=metric.created_at,
    )


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    result = await db.execute(select(Metric).where(Metric.id == metric_id))
    metric = result.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")

    await db.delete(metric)
    await db.commit()


@router.post("/{metric_id}/submit-review")
async def submit_metric_review(
    metric_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_approver),
):
    result = await db.execute(select(Metric).where(Metric.id == metric_id))
    metric = result.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")

    metric.status = "pending_review"
    await db.commit()

    return {"message": "已提交审核", "metric_id": metric_id, "status": metric.status}


@router.post("/{metric_id}/review")
async def review_metric(
    metric_id: int,
    req: DatasetReview,  # reuse the same review structure (status + comment)
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_approver),
):
    result = await db.execute(select(Metric).where(Metric.id == metric_id))
    metric = result.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="指标不存在")

    if metric.status != "pending_review":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能审核待审核状态的指标")

    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="审核结果必须是 approved 或 rejected")

    metric.status = req.status
    await db.commit()

    return {"message": "审核完成", "metric_id": metric_id, "status": metric.status}
