from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DatasetItemCreate(BaseModel):
    input_text: str
    expected_output: str = ""
    scene_label: str = ""
    difficulty: str = "medium"
    metadata_json: str = "{}"


class DatasetItemResponse(BaseModel):
    id: int
    dataset_id: int
    input_text: str
    expected_output: str
    scene_label: str
    difficulty: str
    sort_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    scene: str = "general"
    items: List[DatasetItemCreate] = []


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scene: Optional[str] = None


class DatasetReview(BaseModel):
    status: str  # approved / rejected
    comment: str = ""


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: str
    scene: str
    status: str
    version: str
    item_count: int
    created_by: Optional[int]
    reviewer_id: Optional[int]
    review_comment: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
