from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # em / bleu / rouge_l / f1 / llm_judge / custom_xxx
    description: Mapped[str] = mapped_column(Text, default="")
    metric_type: Mapped[str] = mapped_column(String(32), default="builtin")
    # builtin / llm_based / custom
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    # LLM-as-Judge 配置或自定义代码等
    custom_code: Mapped[str] = mapped_column(Text, default="")
    # 自定义 Python 函数代码片段
    status: Mapped[str] = mapped_column(String(32), default="approved")
    # draft / pending_review / approved / rejected
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
