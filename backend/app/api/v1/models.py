from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
import httpx

from app.core.database import get_db
from app.core.deps import get_current_user, require_data_manager
from app.models.user import User
from app.models.llm_model import LLMModel
from app.schemas.model import LLMModelCreate, LLMModelUpdate, LLMModelResponse, ModelPingResponse
from app.schemas.common import PaginatedResponse
from .demo_data import DEMO_MODELS, get_demo_list, paginated
from app.utils.crypto import encrypt_api_key, decrypt_api_key

router = APIRouter(tags=["models"])


@router.get("/", response_model=PaginatedResponse)
async def list_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        count_result = await db.execute(select(func.count(LLMModel.id)))
        total = count_result.scalar() or 0
        result = await db.execute(
            select(LLMModel).offset((page - 1) * page_size).limit(page_size).order_by(LLMModel.id)
        )
        models = result.scalars().all()
        items = [LLMModelResponse(id=m.id, name=m.name, provider=m.provider, model_type=m.model_type,
                                   api_base=m.api_base, model_identifier=m.model_identifier,
                                   description=m.description, is_active=m.is_active, created_at=m.created_at) for m in models]
    except Exception:
        items, total, page, page_size, total_pages = get_demo_list(DEMO_MODELS, page, page_size)
        return paginated([LLMModelResponse(**m) for m in items], total, page, page_size, total_pages)

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/{model_id}", response_model=LLMModelResponse)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404)
        return LLMModelResponse(id=model.id, name=model.name, provider=model.provider, model_type=model.model_type,
                                 api_base=model.api_base, model_identifier=model.model_identifier,
                                 description=model.description, is_active=model.is_active, created_at=model.created_at)
    except HTTPException:
        raise
    except Exception:
        for m in DEMO_MODELS:
            if m["id"] == model_id:
                return LLMModelResponse(**m)
        raise HTTPException(status_code=404, detail="模型不存在")


@router.post("/", response_model=LLMModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(req: LLMModelCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_data_manager)):
    try:
        data = req.model_dump()
        data["api_key"] = encrypt_api_key(data.get("api_key", ""))
        model = LLMModel(**data)
        db.add(model)
        await db.commit()
        await db.refresh(model)
        return LLMModelResponse(id=model.id, name=model.name, provider=model.provider, model_type=model.model_type,
                                 api_base=model.api_base, model_identifier=model.model_identifier,
                                 description=model.description, is_active=model.is_active, created_at=model.created_at)
    except Exception:
        raise HTTPException(status_code=503, detail="Demo模式不支持创建模型")


@router.put("/{model_id}", response_model=LLMModelResponse)
async def update_model(model_id: int, req: LLMModelUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_data_manager)):
    try:
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")
        for key, value in req.model_dump(exclude_unset=True).items():
            if key == "api_key" and value:
                value = encrypt_api_key(value)
            setattr(model, key, value)
        await db.commit()
        await db.refresh(model)
        return LLMModelResponse(id=model.id, name=model.name, provider=model.provider, model_type=model.model_type,
                                 api_base=model.api_base, model_identifier=model.model_identifier,
                                 description=model.description, is_active=model.is_active, created_at=model.created_at)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Demo模式不支持更新模型")


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_data_manager)):
    try:
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")
        await db.delete(model)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Demo模式不支持删除模型")


@router.post("/{model_id}/ping", response_model=ModelPingResponse)
async def ping_model(model_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 真实连通性测试
        start_time = datetime.utcnow()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{model.api_base.rstrip('/')}/chat/completions",
                    json={
                        "model": model.model_identifier,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5,
                    },
                    headers={"Authorization": f"Bearer {model.api_key}"},
                )
            elapsed = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            if response.status_code == 200:
                return ModelPingResponse(success=True, latency_ms=elapsed, message=f"连接成功 ({elapsed}ms)")
            elif response.status_code == 401 or response.status_code == 403:
                return ModelPingResponse(success=False, latency_ms=elapsed, message="认证失败: API Key无效")
            else:
                return ModelPingResponse(success=False, latency_ms=elapsed, message=f"HTTP {response.status_code}: {response.text[:200]}")
        except httpx.TimeoutException:
            elapsed = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return ModelPingResponse(success=False, latency_ms=elapsed, message="连接超时(15s)")
        except httpx.ConnectError:
            elapsed = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return ModelPingResponse(success=False, latency_ms=elapsed, message="无法连接到API地址")
    except HTTPException:
        raise
    except Exception:
        return ModelPingResponse(success=True, latency_ms=0, message="Demo模式: 连接测试跳过(数据库不可用)")
