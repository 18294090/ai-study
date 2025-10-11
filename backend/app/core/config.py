# 配置设置
# app/core/config.py
import os
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import AnyHttpUrl, EmailStr, PostgresDsn, ValidationError, field_validator
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根路径
ROOT_PATH = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    """应用配置设置类"""    
    # ================== 基础配置 ==================
    PROJECT_NAME: str = "题库管理系统"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Production-Ready FastAPI Project"
    ENV: str = "development"  # development, staging, production
    
    # ================== 服务器配置 ==================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False
    WORKERS: int = 1
    
    # ================== API 配置 ==================
    API_V1_PREFIX: str = "/api/v1"
    API_INTERNAL_PREFIX: str = "/internal"
    
    # ================== 文件上传配置 ==================
    UPLOAD_DIR: str = str(ROOT_PATH / "uploads")
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_UPLOAD_TYPES: List[str] = ["image/jpeg", "image/png", "image/gif"]
    
    # ================== 数据库配置 ==================
    DATABASE_URL: PostgresDsn = PostgresDsn(
        os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:123@localhost:5432/mydb"
        )
    )

    # Alembic 同步数据库配置
    SQLALCHEMY_DATABASE_URL: str = "postgresql://postgres:123@localhost:5432/mydb"

    # 数据库连接配置
    DB_ECHO: bool = False  # SQL 语句日志输出
    CREATE_DB_TABLES: bool = True  # 是否在启动时自动创建数据库表（开发环境可用）
    
    @field_validator("DATABASE_URL")
    def validate_db_url(cls, v: PostgresDsn) -> PostgresDsn:
        """确保数据库URL使用异步驱动"""
        if isinstance(v, MultiHostUrl):
            return v
        if "+asyncpg" not in v.scheme:
            raise ValueError("Database URL must use asyncpg driver")
        return v
    
    # ================== 安全配置 ==================
    SECRET_KEY: str = "secret-key-please-change-for-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    ALGORITHM: str = "HS256"
    
    # CORS 配置
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # ================== 管理员账户 ==================
    FIRST_SUPERUSER: EmailStr = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "changeme"
    
    # ================== 功能开关 ==================
    DOCS_ENABLED: bool = True
    CREATE_DB_TABLES: bool = True  # 生产环境应为False
    TESTING: bool = False  # 测试模式标志
    DEBUG: bool = False
    
    # ================== 日志配置 ==================
    LOG_LEVEL: str = "INFO"
    JSON_LOGS: bool = False  # 是否使用JSON格式日志
    LOG_FILE: Optional[str] = None  # 日志文件路径
    
    # ================== 第三方服务 ==================
    SENTRY_DSN: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    
    # ================== 缓存配置 ==================
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    CACHE_TTL: int = 300  # 5 minutes
    
    # ================== 监控配置 ==================
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_METRICS_PATH: str = "/internal/metrics"
    
    # ================== 任务队列 ==================
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    
    # ================== 文件存储 ==================
    MEDIA_ROOT: str = str(ROOT_PATH / "media")
    MAX_UPLOAD_SIZE: int = 100  # MB
    
    # ================== Neo4j 配置 ==================
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "12345678")

    # ================== 模型配置 ==================
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（带缓存）"""
    try:
        return Settings()
    except ValidationError as e:
        logging.error(f"配置验证错误: {e}")
        raise


def setup_app_logging(config: Settings) -> None:
    """配置应用日志
    此函数是一个代理，实际的日志配置实现在 app.core.logging 模块中
    """
    from app.core.logging import setup_logging
    setup_logging(config)


# 全局配置实例
settings = get_settings()

# 如果直接运行此文件，则打印配置
if __name__ == "__main__":
    import json

    print(PostgresDsn)
    print(json.dumps(settings.model_dump(), indent=2))
