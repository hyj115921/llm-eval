from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvalTask(Base):
    __tablename__ = "eval_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("llm_models.id"), nullable=False)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id"), nullable=False)
    metric_ids: Mapped[str] = mapped_column(String(512), default="")
    # 逗号分隔的指标ID列表
    prompt_content: Mapped[str] = mapped_column(Text, default="")
    # 使用的Prompt内容（快照）
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompts.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending / running / completed / failed / cancelled
    schedule_type: Mapped[str] = mapped_column(String(32), default="immediate")
    # immediate / scheduled
    cron_expression: Mapped[str] = mapped_column(String(128), default="")
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    # 汇总得分
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    # 各指标详细得分
    error_message: Mapped[str] = mapped_column(Text, default="")
    celery_task_id: Mapped[str] = mapped_column(String(256), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    eval_task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("eval_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("dataset_items.id"), nullable=False)
    model_output: Mapped[str] = mapped_column(Text, default="")
    expected_output: Mapped[str] = mapped_column(Text, default="")
    scores_json: Mapped[str] = mapped_column(Text, default="{}")
    # {"em": 1.0, "bleu": 0.85, "rouge_l": 0.92, "llm_judge": 8.5}
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
