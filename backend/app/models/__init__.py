from app.core.database import Base

# 导入所有模型以确保 Alembic 能发现
from app.models.user import User
from app.models.llm_model import LLMModel
from app.models.dataset import Dataset, DatasetItem
from app.models.metric import Metric
from app.models.prompt import Prompt, PromptVersion
from app.models.eval_task import EvalTask, EvalResult
from app.models.optimization import OptimizationTask, OptimizationRound, OptimizationCandidate
from app.models.project import Project
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "User",
    "LLMModel",
    "Dataset", "DatasetItem",
    "Metric",
    "Prompt", "PromptVersion",
    "EvalTask", "EvalResult",
    "OptimizationTask", "OptimizationRound", "OptimizationCandidate",
    "Project",
    "AuditLog",
]
