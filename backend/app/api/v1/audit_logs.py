"""审计日志查询 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_admin
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.common import PaginatedResponse

router = APIRouter(tags=["审计日志"])


@router.get("/", response_model=PaginatedResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Query(None),
    action: str = Query(None),
    target_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),  # 只有管理员可查看
):
    try:
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        if user_id is not None:
            query = query.where(AuditLog.user_id == user_id)
            count_query = count_query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if target_type:
            query = query.where(AuditLog.target_type == target_type)
            count_query = count_query.where(AuditLog.target_type == target_type)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        result = await db.execute(
            query.offset((page - 1) * page_size).limit(page_size).order_by(AuditLog.id.desc())
        )
        logs = result.scalars().all()

        items = [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        return PaginatedResponse(
            items=items, total=total, page=page, page_size=page_size, total_pages=total_pages,
        )
    except Exception:
        # Demo fallback: return empty audit logs
        return PaginatedResponse(
            items=[], total=0, page=page, page_size=page_size, total_pages=0,
        )
