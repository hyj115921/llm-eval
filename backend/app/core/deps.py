from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效或已过期")
    user_id = payload.get("user_id")
    username = payload.get("username", "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token无效")

    # 数据库查询
    try:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if user:
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
            return user
    except Exception:
        pass

    # Demo 模式回退
    if payload.get("demo"):
        user = User(
            id=int(user_id),
            username=username,
            password_hash="",
            email=f"{username}@example.com",
            display_name=payload.get("display_name", username),
            role=payload.get("role", "developer"),
            is_active=True,
        )
        return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


async def require_data_manager(current_user: User = Depends(get_current_user)) -> User:
    """需要数据管理权限（admin / evaluator）才能创建/修改/删除数据集和指标"""
    from app.core.permissions import can_manage_data
    if not can_manage_data(current_user.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要数据管理权限（管理员或评测管理员）")
    return current_user


async def require_task_executor(current_user: User = Depends(get_current_user)) -> User:
    """需要任务执行权限（admin / evaluator / developer）才能创建/启动评测和优化"""
    from app.core.permissions import can_execute_task
    if not can_execute_task(current_user.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要任务执行权限")
    return current_user


async def require_approver(current_user: User = Depends(get_current_user)) -> User:
    """需要审核权限（admin / evaluator）才能审核数据集和指标"""
    from app.core.permissions import can_approve
    if not can_approve(current_user.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要审核权限（管理员或评测管理员）")
    return current_user
