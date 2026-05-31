from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OptimizationTask(Base):
    __tablename__ = "optimization_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompts.id"), nullable=True)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("llm_models.id"), nullable=False)
    # 评测模型
    optimizer_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("llm_models.id"), nullable=False)
    # 优化器模型
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id"), nullable=False)
    metric_ids: Mapped[str] = mapped_column(String(512), default="")
    initial_prompt: Mapped[str] = mapped_column(Text, default="")
    best_prompt: Mapped[str] = mapped_column(Text, default="")
    best_score: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_score: Mapped[float] = mapped_column(Float, default=0.0)
    max_rounds: Mapped[int] = mapped_column(Integer, default=10)
    candidates_per_round: Mapped[int] = mapped_column(Integer, default=3)
    convergence_threshold: Mapped[float] = mapped_column(Float, default=0.01)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending / running / completed / failed / cancelled
    score_history_json: Mapped[str] = mapped_column(Text, default="[]")
    # 每轮最优分数记录
    celery_task_id: Mapped[str] = mapped_column(String(256), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class OptimizationRound(Base):
    __tablename__ = "optimization_rounds"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    optimization_task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_before: Mapped[str] = mapped_column(Text, default="")
    best_prompt_after: Mapped[str] = mapped_column(Text, default="")
    score_before: Mapped[float] = mapped_column(Float, default=0.0)
    score_after: Mapped[float] = mapped_column(Float, default=0.0)
    candidates_json: Mapped[str] = mapped_column(Text, default="[]")
    # 本轮生成的候选 Prompt 列表
    error_samples_json: Mapped[str] = mapped_column(Text, default="[]")
    # 本轮错误样本
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OptimizationCandidate(Base):
    __tablename__ = "optimization_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    optimization_round_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_content: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    scores_detail: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
