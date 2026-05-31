from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PromptCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    scene: str = "general"
    content: str = ""
    project_id: Optional[int] = None


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class PromptResponse(BaseModel):
    id: int
    name: str
    description: str
    scene: str
    current_version: str
    current_content: str
    best_score: float
    project_id: Optional[int]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PromptVersionResponse(BaseModel):
    id: int
    prompt_id: int
    version: str
    content: str
    score: float
    source: str
    optimization_task_id: Optional[int]
    created_at: datetime
    model_config = {"from_attributes": True}


# 优化策略预设
OPTIMIZATION_STRATEGIES = {
    "conservative": {"max_rounds": 5, "candidates_per_round": 2, "convergence_threshold": 0.005,
                     "description": "保守模式：小步迭代，精细调优，适合已有较好Prompt的微调"},
    "balanced": {"max_rounds": 10, "candidates_per_round": 3, "convergence_threshold": 0.01,
                 "description": "均衡模式：兼顾探索深度和效率，适合大多数场景"},
    "aggressive": {"max_rounds": 15, "candidates_per_round": 5, "convergence_threshold": 0.02,
                   "description": "激进模式：大幅探索，更快收敛条件，适合初始Prompt质量较差的场景"},
}


class OptimizationTaskCreate(BaseModel):
    name: str
    project_id: Optional[int] = None
    prompt_id: Optional[int] = None
    model_id: int
    optimizer_model_id: int
    dataset_id: int
    metric_ids: str = ""
    initial_prompt: str
    strategy: str = "balanced"  # conservative / balanced / aggressive
    max_rounds: int = 0  # 0=按策略预设
    candidates_per_round: int = 0  # 0=按策略预设
    convergence_threshold: float = 0.0  # 0=按策略预设


class OptimizationTaskResponse(BaseModel):
    id: int
    name: str
    project_id: Optional[int]
    model_id: int
    optimizer_model_id: int
    dataset_id: int
    initial_prompt: str
    best_prompt: str
    best_score: float
    baseline_score: float
    max_rounds: int
    current_round: int
    status: str
    score_history_json: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


class OptimizationRoundResponse(BaseModel):
    id: int
    optimization_task_id: int
    round_number: int
    prompt_before: str
    best_prompt_after: str
    score_before: float
    score_after: float
    candidates_json: str
    error_samples_json: str
    created_at: datetime
    model_config = {"from_attributes": True}
