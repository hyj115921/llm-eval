from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "llm_eval",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.eval_tasks",
        "app.tasks.optimization_tasks",
        "app.tasks.scheduler",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    beat_schedule={
        # 每分钟扫描一次待执行的定时评测任务
        "scan-scheduled-eval-tasks": {
            "task": "scheduler.scan_scheduled_tasks",
            "schedule": crontab(minute="*"),
        },
    },
)
