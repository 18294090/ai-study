"""响应模型模块

定义API响应的标准数据结构
"""

from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")

class ResponseBase(BaseModel):
    """响应基类"""
    code: int = 0
    message: str = "Success"
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 0,
                "message": "Success"
            }
        }
    )

class DataResponse(ResponseBase, Generic[DataT]):
    """带数据的响应模型"""
    data: DataT
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 0,
                "message": "Success",
                "data": {
                    "id": 1,
                    "name": "示例数据"
                }
            }
        }
    )

class PageResponse(ResponseBase, Generic[DataT]):
    """分页响应模型"""
    code: int = 0
    data: DataT
    total: int
    page: int = 1
    size: int = 20
    pages: int = 1

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 200,
                "message": "Success",
                "data": [],
                "total": 100,
                "page": 1,
                "size": 20,
                "pages": 5
            }
        }
    )

class ErrorResponse(ResponseBase):
    """错误响应模型"""
    code: int = 400
    message: str = "Error"
    detail: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 400,
                "message": "请求错误",
                "detail": "详细错误信息"
            }
        }
    )

class PageResponse(DataResponse[DataT], Generic[DataT]):
    """分页响应模型"""
    total: int
    page: int
    size: int
    pages: int
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 200,
                "message": "Success",
                "data": [
                    {
                        "id": 1,
                        "name": "示例数据1"
                    },
                    {
                        "id": 2,
                        "name": "示例数据2"
                    }
                ],
                "total": 100,
                "page": 1,
                "size": 10,
                "pages": 10
            }
        }
    )

class UploadResponse(ResponseBase):
    """文件上传响应模型"""
    data: dict[str, str]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 200,
                "message": "Success",
                "data": {
                    "url": "http://localhost:8000/uploads/example.jpg"
                }
            }
        }
    )