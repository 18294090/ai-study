# Celery 任务配置和定义
from celery import Celery
from app.core.config import settings

# 创建Celery应用实例
celery_app = Celery(
    "ai_study",
    broker=settings.CELERY_BROKER_URL,  # Redis URL
    backend=settings.CELERY_RESULT_BACKEND,  # Redis URL
    include=["app.tasks.tasks"]  # 包含任务模块
)

# Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
