"""
审计日志工具 — 记录所有关键操作，满足企业合规要求。
"""
import logging
from typing import Optional

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def audit_log(
    db,
    user_id: Optional[int],
    username: str,
    action: str,
    target_type: str = "",
    target_id: Optional[int] = None,
    detail: str = "",
    ip_address: str = "",
):
    """写入审计日志。异步安全，失败不影响主流程。"""
    try:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        # 审计失败不应中断业务
        logger.warning("审计日志写入失败: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass


# ====== 预定义操作类型 ======

# 数据集
ACTION_DATASET_CREATE = "dataset.create"
ACTION_DATASET_UPDATE = "dataset.update"
ACTION_DATASET_DELETE = "dataset.delete"
ACTION_DATASET_SUBMIT_REVIEW = "dataset.submit_review"
ACTION_DATASET_APPROVE = "dataset.approve"
ACTION_DATASET_REJECT = "dataset.reject"
ACTION_DATASET_IMPORT = "dataset.import"

# 评测标准
ACTION_METRIC_CREATE = "metric.create"
ACTION_METRIC_UPDATE = "metric.update"
ACTION_METRIC_DELETE = "metric.delete"
ACTION_METRIC_SUBMIT_REVIEW = "metric.submit_review"
ACTION_METRIC_APPROVE = "metric.approve"
ACTION_METRIC_REJECT = "metric.reject"

# 模型
ACTION_MODEL_CREATE = "model.create"
ACTION_MODEL_UPDATE = "model.update"
ACTION_MODEL_DELETE = "model.delete"

# 评测任务
ACTION_EVAL_CREATE = "eval.create"
ACTION_EVAL_START = "eval.start"
ACTION_EVAL_CANCEL = "eval.cancel"
ACTION_EVAL_DELETE = "eval.delete"

# Prompt 优化
ACTION_OPTIMIZATION_CREATE = "optimization.create"
ACTION_OPTIMIZATION_START = "optimization.start"
ACTION_OPTIMIZATION_CANCEL = "optimization.cancel"

# 项目
ACTION_PROJECT_CREATE = "project.create"
ACTION_PROJECT_DELETE = "project.delete"

# 用户
ACTION_USER_CREATE = "user.create"
ACTION_USER_UPDATE = "user.update"
ACTION_USER_DELETE = "user.delete"
ACTION_USER_LOGIN = "user.login"
