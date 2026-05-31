from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+asyncmy://llm_eval_user:llm_eval_pass@localhost:3306/llm_eval"
    REDIS_URL: str = "redis://:redis123456@localhost:6379/0"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin123"
    MINIO_BUCKET: str = "llm-eval-data"
    MINIO_SECURE: bool = False

    JWT_SECRET_KEY: str = "llm-eval-platform-jwt-secret-key-2024"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Demo 模式：设为 False 时，所有 API 强制要求数据库，失败就明确报错
    DEMO_MODE: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
