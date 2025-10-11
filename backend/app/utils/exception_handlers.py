"""异常处理器模块

提供全局异常处理器，用于统一处理应用中的各种异常
包括:
- HTTP异常
- 验证错误
- 数据库异常
- 权限错误
- 自定义业务异常
- 未处理的异常
"""
import sys
import traceback
from typing import Any, Dict, Optional, Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.schemas.response import ErrorResponse

logger = get_logger(__name__)

async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """HTTP异常处理器
    
    处理FastAPI的HTTPException异常
    
    参数:
        request: FastAPI请求对象
        exc: HTTP异常实例
        
    返回:
        JSONResponse: 统一格式的错误响应
    """
    status_code = getattr(exc, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = getattr(exc, 'detail', str(exc))
    headers = getattr(exc, 'headers', None)
    
    logger.error(
        f"HTTP异常 - 路径: {request.url.path} - 状态码: {status_code} - 详情: {detail}"
    )
    
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            code=status_code,
            message="请求错误",
            detail=detail
        ).model_dump(),
        headers=headers,
    )

async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """验证异常处理器
    
    处理请求参数验证错误和Pydantic模型验证错误
    
    参数:
        request: FastAPI请求对象
        exc: 验证异常实例
        
    返回:
        JSONResponse: 统一格式的错误响应
    """
    if not isinstance(exc, (RequestValidationError, ValidationError)):
        raise exc
    errors = []
    for error in exc.errors():
        error_location = " -> ".join(str(loc) for loc in error["loc"])
        error_msg = f"{error_location}: {error['msg']}"
        errors.append(error_msg)
    
    detail = "; ".join(errors)
    logger.warning(
        f"验证错误 - 路径: {request.url.path} - 详情: {detail}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="数据验证错误",
            detail=detail
        ).model_dump(),
    )

async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    """数据库异常处理器
    
    处理SQLAlchemy相关的数据库异常
    
    参数:
        request: FastAPI请求对象
        exc: 数据库异常实例
        
    返回:
        JSONResponse: 统一格式的错误响应
    """
    error_msg = str(exc)
    logger.error(
        f"数据库错误 - 路径: {request.url.path} - 详情: {error_msg}",
        exc_info=exc
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="数据库操作失败",
            detail="数据库操作时发生错误" if not request.app.debug else error_msg
        ).model_dump(),
    )

class AppException(Exception):
    """应用自定义异常基类"""
    def __init__(
        self,
        message: str,
        code: int = status.HTTP_400_BAD_REQUEST,
        detail: Optional[str] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.detail = detail or message
        super().__init__(self.detail)

async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    """应用自定义异常处理器
    
    处理应用中抛出的自定义异常
    
    参数:
        request: FastAPI请求对象
        exc: 自定义异常实例
        
    返回:
        JSONResponse: 统一格式的错误响应
    """
    logger.error(
        f"应用异常 - 路径: {request.url.path} - "
        f"代码: {exc.code} - 消息: {exc.message} - 详情: {exc.detail}"
    )
    
    return JSONResponse(
        status_code=exc.code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            detail=exc.detail
        ).model_dump(),
    )

async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """未处理异常处理器
    
    处理所有其他未被特定处理器捕获的异常
    
    参数:
        request: FastAPI请求对象
        exc: 异常实例
        
    返回:
        JSONResponse: 统一格式的错误响应
    """
    exc_info = sys.exc_info()
    if exc_info[0] is not None:
        exception_details = "".join(
            traceback.format_exception(
                exc_info[0],
                exc_info[1],
                exc_info[2]
            )
        )
        exc_type_name = exc_info[0].__name__
    else:
        exception_details = traceback.format_exc()
        exc_type_name = type(exc).__name__

    logger.error(
        f"未处理异常 - 路径: {request.url.path} - 类型: {exc_type_name} - "
        f"详情: {str(exc)}\n{exception_details}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="服务器内部错误",
            detail="服务器发生未知错误" if not request.app.debug else str(exc)
        ).model_dump(),
    )

def setup_exception_handlers(app: Any) -> None:
    """配置异常处理器
    
    为FastAPI应用添加全局异常处理器
    
    参数:
        app: FastAPI应用实例
    """
    from fastapi.exception_handlers import (
        http_exception_handler as fastapi_http_exception_handler,
        request_validation_exception_handler as fastapi_validation_exception_handler,
    )
    from fastapi import HTTPException
    
    # 处理HTTP异常
    app.add_exception_handler(HTTPException, fastapi_http_exception_handler)
    
    # 处理验证异常
    app.add_exception_handler(RequestValidationError, fastapi_validation_exception_handler)
    
    # 处理数据库异常
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    
    # 处理自定义应用异常
    app.add_exception_handler(AppException, app_exception_handler)
    
    # 处理未捕获的异常
    app.add_exception_handler(Exception, unhandled_exception_handler)