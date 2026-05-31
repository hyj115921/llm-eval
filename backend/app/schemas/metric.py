from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MetricCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=1, max_length=64)
    description: str = ""
    metric_type: str = "builtin"
    config_json: str = "{}"
    custom_code: str = ""


class MetricUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config_json: Optional[str] = None
    custom_code: Optional[str] = None
    is_active: Optional[bool] = None


class MetricResponse(BaseModel):
    id: int
    name: str
    code: str
    description: str
    metric_type: str
    config_json: str
    status: str
    is_active: bool
    created_by: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}
