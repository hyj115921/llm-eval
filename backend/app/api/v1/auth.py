from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.utils.audit import audit_log, ACTION_USER_LOGIN

router = APIRouter(tags=["auth"])

# Demo 模式：数据库不可用时使用内存用户
DEMO_USERS = {
    "admin": {
        "id": 1, "username": "admin", "password_hash": get_password_hash("admin123"),
        "email": "admin@example.com", "display_name": "超级管理员", "role": "admin",
        "is_active": True, "created_at": datetime.utcnow(),
    },
    "evaluator": {
        "id": 2, "username": "evaluator", "password_hash": get_password_hash("eval123"),
        "email": "evaluator@example.com", "display_name": "评测管理员", "role": "evaluator",
        "is_active": True, "created_at": datetime.utcnow(),
    },
    "developer": {
        "id": 3, "username": "developer", "password_hash": get_password_hash("dev123"),
        "email": "developer@example.com", "display_name": "开发者", "role": "developer",
        "is_active": True, "created_at": datetime.utcnow(),
    },
}


def _make_token(user_data: dict) -> str:
    return create_access_token(data={
        "user_id": str(user_data["id"]),
        "username": user_data["username"],
        "role": user_data["role"],
        "demo": True,
    })


def _user_response(user_data: dict) -> UserResponse:
    return UserResponse(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data["email"],
        display_name=user_data["display_name"],
        role=user_data["role"],
        is_active=user_data["is_active"],
        created_at=user_data["created_at"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 尝试数据库登录
    try:
        result = await db.execute(select(User).where(User.username == req.username))
        user = result.scalar_one_or_none()
        if user and verify_password(req.password, user.password_hash):
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
            access_token = create_access_token(data={"user_id": str(user.id), "username": user.username})
            await audit_log(db, user.id, user.username, ACTION_USER_LOGIN,
                            target_type="user", target_id=user.id,
                            detail=f"用户登录: {user.username}")
            return TokenResponse(access_token=access_token, token_type="bearer", user=UserResponse(
                id=user.id, username=user.username, email=user.email,
                display_name=user.display_name, role=user.role,
                is_active=user.is_active, created_at=user.created_at,
            ))
    except Exception:
        pass  # 数据库不可用，回退到 demo 模式

    # Demo 模式回退
    demo_user = DEMO_USERS.get(req.username)
    if not demo_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误（Demo模式用户: admin/evaluator/developer）")
    if not verify_password(req.password, demo_user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    access_token = _make_token(demo_user)
    return TokenResponse(access_token=access_token, token_type="bearer", user=_user_response(demo_user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: UserCreate, db: AsyncSession = Depends(get_db)):
    # 1. 尝试数据库注册
    try:
        result = await db.execute(select(User).where(User.username == req.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
        user = User(
            username=req.username, password_hash=get_password_hash(req.password),
            email=req.email or "", display_name=req.display_name or "", role=req.role or "developer",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        access_token = create_access_token(data={"user_id": str(user.id), "username": user.username})
        return TokenResponse(
            access_token=access_token, token_type="bearer",
            user=UserResponse(
                id=user.id, username=user.username, email=user.email,
                display_name=user.display_name, role=user.role,
                is_active=user.is_active, created_at=user.created_at,
            ),
        )
    except HTTPException:
        raise
    except Exception:
        pass  # 数据库不可用，回退到 demo 内存注册

    # 2. Demo 模式内存注册
    if req.username in DEMO_USERS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    new_id = max(u["id"] for u in DEMO_USERS.values()) + 1
    new_user = {
        "id": new_id,
        "username": req.username,
        "password_hash": get_password_hash(req.password),
        "email": req.email or "",
        "display_name": req.display_name or req.username,
        "role": "developer",
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    DEMO_USERS[req.username] = new_user
    access_token = _make_token(new_user)
    return TokenResponse(access_token=access_token, token_type="bearer", user=_user_response(new_user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id, username=current_user.username,
        email=current_user.email, display_name=current_user.display_name,
        role=current_user.role, is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
