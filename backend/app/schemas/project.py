from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    project_type: str = "chat"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str
    project_type: str
    status: str
    created_by: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


class ProjectDashboard(BaseModel):
    project: ProjectResponse
    dataset_count: int = 0
    eval_task_count: int = 0
    optimization_task_count: int = 0
    best_prompt_score: float = 0.0
    latest_eval_scores: str = "{}"
