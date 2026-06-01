from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：不自动创建表，统一用 Alembic migration 管理
    yield
    # 关闭时
    await engine.dispose()


app = FastAPI(
    title="大模型能力评测与Prompt自动调优系统",
    description="企业级大模型能力评测管理与Prompt调优平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "llm-eval-platform"}


# 注册路由
from app.api.v1 import auth, users, models, datasets, metrics, evals, prompts, projects, reports, audit_logs, ws

app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户管理"])
app.include_router(models.router, prefix="/api/v1/models", tags=["模型管理"])
app.include_router(datasets.router, prefix="/api/v1/datasets", tags=["数据集管理"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["评测标准管理"])
app.include_router(evals.router, prefix="/api/v1/evals", tags=["评测任务"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["Prompt调优"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["项目管理"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["评测报告"])
app.include_router(audit_logs.router, prefix="/api/v1/audit-logs", tags=["审计日志"])
app.include_router(ws.router, prefix="/api/v1/ws", tags=["WebSocket"])
