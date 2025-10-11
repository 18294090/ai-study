"""
日志配置模块

这个模块提供了应用程序的日志配置功能，包括：
- 日志系统的初始化和配置
- 支持控制台和文件输出
- 支持JSON格式日志
- 日志级别控制
- 第三方库的日志管理
"""
import sys
import logging
import logging.config
import logging.handlers
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache
from fastapi import Request
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.log import OperationLog

def setup_logging(config: Settings) -> None:
    """配置应用日志系统
    
    参数:
        config: Settings 实例，包含日志配置选项
    
    功能:
        - 支持控制台和文件日志输出
        - 支持JSON格式日志
        - 自动日志文件轮转
        - 针对生产环境优化第三方库的日志级别
        - 提供基础错误处理和回退机制
    """
    try:
        # 设置基本变量
        log_level: str = config.LOG_LEVEL.upper()
        json_logs: bool = config.JSON_LOGS
        
        # 定义基本的格式化器
        formatters: Dict[str, Dict[str, str]] = {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        }
        
        # 如果启用了JSON日志，添加JSON格式化器
        if json_logs:
            formatters["json"] = {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(funcName)s %(lineno)s"
            }
        
        # 定义处理器
        handlers: Dict[str, Dict[str, Any]] = {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if json_logs else "default",
                "stream": "ext://sys.stdout"
            }
        }
        
        # 如果配置了日志文件，添加文件处理器
        if config.LOG_FILE:
            handlers["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": config.LOG_FILE,
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "formatter": "json" if json_logs else "default",
                "encoding": "utf-8"
            }
        
        # 定义日志配置
        log_config: Dict[str, Any] = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,
            "handlers": handlers,
            "loggers": {
                "app": {
                    "handlers": list(handlers.keys()),
                    "level": log_level,
                    "propagate": False
                },
                "uvicorn": {
                    "handlers": list(handlers.keys()),
                    "level": log_level,
                    "propagate": False
                },
                "uvicorn.error": {
                    "level": log_level,
                    "propagate": True
                }
            },
            "root": {
                "handlers": list(handlers.keys()),
                "level": log_level
            }
        }
        
        # 应用日志配置
        logging.config.dictConfig(log_config)
        
        # 设置第三方库的日志级别
        third_party_loggers: List[str] = [
            "sqlalchemy",
            "aioredis",
            "celery",
            "urllib3",
            "httpx",
            "asyncio"
        ]
        
        for logger_name in third_party_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.WARNING if config.ENV == "production" else logging.INFO)
        
        # 记录日志配置完成
        logging.getLogger(__name__).info(
            f"Logging setup completed. Level: {log_level}, JSON format: {json_logs}"
        )
        
    except Exception as e:
        # 如果配置失败，设置基本的控制台日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.error(f"Failed to configure logging: {str(e)}")

@lru_cache(maxsize=None)
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取指定名称的日志记录器
    
    此函数使用 lru_cache 装饰器确保相同名称的记录器只创建一次。
    
    参数:
        name: 日志记录器名称，通常使用 __name__
             如果为 None，返回 root logger
    
    返回:
        logging.Logger: 配置好的日志记录器实例
        
    示例:
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条信息日志")
        >>> logger.error("这是一条错误日志")
    """
    if name is None:
        return logging.getLogger()
    return logging.getLogger(name)

async def log_operation(
    request: Request,
    user_id: int,
    operation: str,
    db: AsyncSession
):
    """记录用户操作"""
    log = OperationLog(
        user_id=user_id,
        operation=operation,
        path=str(request.url),
        method=request.method,
        ip_address=request.client.host,
        timestamp=datetime.utcnow()
    )
    db.add(log)
    await db.commit()