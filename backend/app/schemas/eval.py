from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EvalTaskCreate(BaseModel):
    name: str = Field(..., min_length=1)
    project_id: Optional[int] = None
    model_id: int
    dataset_id: int
    metric_ids: str = ""  # comma-separated
    prompt_content: str = ""
    prompt_id: Optional[int] = None
    schedule_type: str = "immediate"  # immediate / scheduled
    cron_expression: str = ""


class EvalTaskResponse(BaseModel):
    id: int
    name: str
    project_id: Optional[int]
    model_id: int
    dataset_id: int
    metric_ids: str
    prompt_content: str
    prompt_id: Optional[int]
    status: str
    schedule_type: str
    cron_expression: str
    total_items: int
    completed_items: int
    overall_score: float
    error_message: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


class EvalResultResponse(BaseModel):
    id: int
    eval_task_id: int
    dataset_item_id: int
    model_output: str
    expected_output: str
    scores_json: str
    latency_ms: int
    error_message: str
    created_at: datetime
    model_config = {"from_attributes": True}
