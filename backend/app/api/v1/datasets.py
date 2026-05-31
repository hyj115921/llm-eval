from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user, require_data_manager, require_approver
from app.models.user import User
from app.models.dataset import Dataset, DatasetItem
from app.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetReview,
    DatasetResponse,
    DatasetItemCreate,
    DatasetItemResponse,
)
from app.schemas.common import PaginatedResponse
from .demo_data import DEMO_DATASETS, get_demo_list, paginated
from app.utils.audit import audit_log, ACTION_DATASET_CREATE, ACTION_DATASET_UPDATE, \
    ACTION_DATASET_DELETE, ACTION_DATASET_SUBMIT_REVIEW, ACTION_DATASET_APPROVE, \
    ACTION_DATASET_REJECT

router = APIRouter(tags=["datasets"])


@router.get("/", response_model=PaginatedResponse)
async def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    scene: str = Query(None, description="Filter by scene"),
    status: str = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        query = select(Dataset)
        count_query = select(func.count(Dataset.id))

        if scene:
            query = query.where(Dataset.scene == scene)
            count_query = count_query.where(Dataset.scene == scene)
        if status:
            query = query.where(Dataset.status == status)
            count_query = count_query.where(Dataset.status == status)

        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        result = await db.execute(
            query.offset((page - 1) * page_size).limit(page_size).order_by(Dataset.id.desc())
        )
        datasets = result.scalars().all()

        items = [
            DatasetResponse(
                id=d.id,
                name=d.name,
                description=d.description,
                scene=d.scene,
                status=d.status,
                version=d.version,
                item_count=d.item_count,
                created_by=d.created_by,
                reviewer_id=d.reviewer_id,
                review_comment=d.review_comment,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in datasets
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
        items, total, _, _, total_pages = get_demo_list(DEMO_DATASETS, page, page_size)
        return paginated([DatasetResponse(**item) for item in items], total, page, page_size, total_pages)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")

        return DatasetResponse(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            scene=dataset.scene,
            status=dataset.status,
            version=dataset.version,
            item_count=dataset.item_count,
            created_by=dataset.created_by,
            reviewer_id=dataset.reviewer_id,
            review_comment=dataset.review_comment,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        for ds in DEMO_DATASETS:
            if ds["id"] == dataset_id:
                return DatasetResponse(**ds)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")


@router.post("/", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    req: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    try:
        dataset = Dataset(
            name=req.name,
            description=req.description or "",
            scene=req.scene or "general",
            created_by=current_user.id,
        )
        db.add(dataset)
        await db.flush()

        for idx, item_data in enumerate(req.items):
            item = DatasetItem(
                dataset_id=dataset.id,
                input_text=item_data.input_text,
                expected_output=item_data.expected_output or "",
                scene_label=item_data.scene_label or "",
                difficulty=item_data.difficulty or "medium",
                metadata_json=item_data.metadata_json or "{}",
                sort_order=idx,
            )
            db.add(item)

        dataset.item_count = len(req.items)
        await db.commit()
        await db.refresh(dataset)

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_DATASET_CREATE, target_type="dataset",
                        target_id=dataset.id, detail=f"创建数据集: {dataset.name}")

        return DatasetResponse(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            scene=dataset.scene,
            status=dataset.status,
            version=dataset.version,
            item_count=dataset.item_count,
            created_by=dataset.created_by,
            reviewer_id=dataset.reviewer_id,
            review_comment=dataset.review_comment,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int,
    req: DatasetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    try:
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")

        # 已发布/已审核的数据集不可直接修改，需创建新版本
        if dataset.status in ("published", "approved"):
            # 解析当前版本号并递增
            current_ver = dataset.version
            try:
                ver_num = int(current_ver.lstrip("v")) + 1
            except ValueError:
                ver_num = 2
            new_version = f"v{ver_num}"

            # 复制数据集
            new_dataset = Dataset(
                name=req.name if req.name is not None else dataset.name,
                description=req.description if req.description is not None else dataset.description,
                scene=req.scene if req.scene is not None else dataset.scene,
                status="draft",  # 新版本初始为草稿
                version=new_version,
                item_count=dataset.item_count,
                file_url=dataset.file_url,
                created_by=current_user.id,
            )
            db.add(new_dataset)
            await db.flush()

            # 复制所有条目
            items_result = await db.execute(
                select(DatasetItem).where(DatasetItem.dataset_id == dataset.id)
            )
            for old_item in items_result.scalars().all():
                new_item = DatasetItem(
                    dataset_id=new_dataset.id,
                    input_text=old_item.input_text,
                    expected_output=old_item.expected_output,
                    scene_label=old_item.scene_label,
                    difficulty=old_item.difficulty,
                    metadata_json=old_item.metadata_json,
                    sort_order=old_item.sort_order,
                )
                db.add(new_item)

            await db.commit()
            await db.refresh(new_dataset)

            await audit_log(db, current_user.id, current_user.username,
                            ACTION_DATASET_UPDATE, target_type="dataset",
                            target_id=new_dataset.id, detail=f"更新数据集(新版本): {new_dataset.name}")

            return DatasetResponse(
                id=new_dataset.id, name=new_dataset.name, description=new_dataset.description,
                scene=new_dataset.scene, status=new_dataset.status, version=new_dataset.version,
                item_count=new_dataset.item_count, created_by=new_dataset.created_by,
                reviewer_id=None, review_comment="",
                created_at=new_dataset.created_at, updated_at=new_dataset.updated_at,
            )

        # 草稿/已驳回状态可直接修改
        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(dataset, key, value)

        await db.commit()
        await db.refresh(dataset)

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_DATASET_UPDATE, target_type="dataset",
                        target_id=dataset.id, detail=f"更新数据集: {dataset.name}")

        return DatasetResponse(
            id=dataset.id, name=dataset.name, description=dataset.description,
            scene=dataset.scene, status=dataset.status, version=dataset.version,
            item_count=dataset.item_count, created_by=dataset.created_by,
            reviewer_id=dataset.reviewer_id, review_comment=dataset.review_comment,
            created_at=dataset.created_at, updated_at=dataset.updated_at,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    try:
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")

        await db.delete(dataset)
        await db.commit()

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_DATASET_DELETE, target_type="dataset",
                        target_id=dataset_id, detail=f"删除数据集: {dataset.name}")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.post("/{dataset_id}/submit-review")
async def submit_dataset_review(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_approver),
):
    try:
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")

        dataset.status = "pending_review"
        await db.commit()

        await audit_log(db, current_user.id, current_user.username,
                        ACTION_DATASET_SUBMIT_REVIEW, target_type="dataset",
                        target_id=dataset_id, detail=f"提交数据集审核: {dataset.name}")

        return {"message": "已提交审核", "dataset_id": dataset_id, "status": dataset.status}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.post("/{dataset_id}/review")
async def review_dataset(
    dataset_id: int,
    req: DatasetReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_approver),
):
    try:
        result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")

        if dataset.status != "pending_review":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能审核待审核状态的数据集")

        if req.status not in ("approved", "rejected"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="审核结果必须是 approved 或 rejected")

        dataset.status = req.status
        dataset.review_comment = req.comment or ""
        dataset.reviewer_id = current_user.id
        await db.commit()

        review_action = ACTION_DATASET_APPROVE if req.status == "approved" else ACTION_DATASET_REJECT
        await audit_log(db, current_user.id, current_user.username,
                        review_action, target_type="dataset",
                        target_id=dataset_id, detail=f"数据集审核: {dataset.name} ({req.status})")

        return {
            "message": "审核完成",
            "dataset_id": dataset_id,
            "status": dataset.status,
            "comment": req.comment,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.get("/{dataset_id}/items", response_model=PaginatedResponse)
async def list_dataset_items(
    dataset_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        dataset_result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = dataset_result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")

        count_result = await db.execute(
            select(func.count(DatasetItem.id)).where(DatasetItem.dataset_id == dataset_id)
        )
        total = count_result.scalar() or 0

        result = await db.execute(
            select(DatasetItem)
            .where(DatasetItem.dataset_id == dataset_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(DatasetItem.sort_order)
        )
        items_db = result.scalars().all()

        items = [
            DatasetItemResponse(
                id=item.id,
                dataset_id=item.dataset_id,
                input_text=item.input_text,
                expected_output=item.expected_output,
                scene_label=item.scene_label,
                difficulty=item.difficulty,
                sort_order=item.sort_order,
                created_at=item.created_at,
            )
            for item in items_db
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
        dataset = None
        for ds in DEMO_DATASETS:
            if ds["id"] == dataset_id:
                dataset = ds
                break
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
        items, total, _, _, total_pages = get_demo_list(dataset["items"], page, page_size)
        return paginated([DatasetItemResponse(**item) for item in items], total, page, page_size, total_pages)


@router.post("/{dataset_id}/items", response_model=PaginatedResponse, status_code=status.HTTP_201_CREATED)
async def add_dataset_items(
    dataset_id: int,
    items: list[DatasetItemCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    try:
        dataset_result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = dataset_result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
        if dataset.status in ("published", "approved"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已发布/已审核的数据集不能直接修改条目，请创建新版本后再编辑")

        max_order_result = await db.execute(
            select(func.max(DatasetItem.sort_order)).where(DatasetItem.dataset_id == dataset_id)
        )
        max_order = max_order_result.scalar() or 0

        for idx, item_data in enumerate(items):
            item = DatasetItem(
                dataset_id=dataset_id,
                input_text=item_data.input_text,
                expected_output=item_data.expected_output or "",
                scene_label=item_data.scene_label or "",
                difficulty=item_data.difficulty or "medium",
                metadata_json=item_data.metadata_json or "{}",
                sort_order=max_order + idx + 1,
            )
            db.add(item)

        dataset.item_count = dataset.item_count + len(items)
        await db.commit()

        count_result = await db.execute(
            select(func.count(DatasetItem.id)).where(DatasetItem.dataset_id == dataset_id)
        )
        total = count_result.scalar() or 0

        result = await db.execute(
            select(DatasetItem)
            .where(DatasetItem.dataset_id == dataset_id)
            .order_by(DatasetItem.sort_order)
            .limit(20)
        )
        items_db = result.scalars().all()

        items_out = [
            DatasetItemResponse(
                id=item_db.id,
                dataset_id=item_db.dataset_id,
                input_text=item_db.input_text,
                expected_output=item_db.expected_output,
                scene_label=item_db.scene_label,
                difficulty=item_db.difficulty,
                sort_order=item_db.sort_order,
                created_at=item_db.created_at,
            )
            for item_db in items_db
        ]

        total_pages = (total + 20 - 1) // 20
        return PaginatedResponse(
            items=items_out,
            total=total,
            page=1,
            page_size=20,
            total_pages=total_pages,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.delete("/{dataset_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset_item(
    dataset_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    try:
        result = await db.execute(
            select(DatasetItem).where(
                DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据项不存在")

        dataset_result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = dataset_result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
        if dataset.status in ("published", "approved"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已发布/已审核的数据集不能直接删除条目，请创建新版本后再编辑")
        if dataset:
            dataset.item_count = max(0, dataset.item_count - 1)

        await db.delete(item)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Demo模式不支持此操作")


@router.post("/{dataset_id}/import")
async def import_dataset_items(
    dataset_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_data_manager),
):
    """批量导入数据 — 支持 CSV / JSONL / Excel"""
    from app.utils.importer import detect_and_parse

    try:
        dataset_result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
        dataset = dataset_result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据集不存在")
        if dataset.status in ("published", "approved"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已发布数据集不能直接导入，请创建新版本后再操作")

        content = await file.read()
        items_data, fmt_name = detect_and_parse(file.filename or "data.csv", content)

        if not items_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件中未找到有效数据")

        max_order_result = await db.execute(
            select(func.max(DatasetItem.sort_order)).where(DatasetItem.dataset_id == dataset_id)
        )
        max_order = max_order_result.scalar() or 0

        added = 0
        for idx, item_data in enumerate(items_data):
            item = DatasetItem(
                dataset_id=dataset_id,
                input_text=item_data["input_text"],
                expected_output=item_data.get("expected_output", ""),
                scene_label=item_data.get("scene_label", ""),
                difficulty=item_data.get("difficulty", "medium"),
                sort_order=max_order + idx + 1,
            )
            db.add(item)
            added += 1

        dataset.item_count = dataset.item_count + added
        await db.commit()

        return {
            "success": True,
            "format": fmt_name,
            "imported": added,
            "total_items": dataset.item_count,
            "message": f"成功从 {fmt_name} 文件导入 {added} 条数据",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"导入失败: {str(e)}")
