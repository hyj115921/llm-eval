from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LLMModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(..., min_length=1, max_length=64)
    model_type: str = "chat"
    api_base: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    model_identifier: str = Field(..., min_length=1)
    description: str = ""


class LLMModelUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model_type: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    model_identifier: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class LLMModelResponse(BaseModel):
    id: int
    name: str
    provider: str
    model_type: str
    api_base: str
    model_identifier: str
    description: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelPingResponse(BaseModel):
    success: bool
    latency_ms: int
    message: str
