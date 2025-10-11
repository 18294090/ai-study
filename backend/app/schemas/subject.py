from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SubjectBase(BaseModel):
    """科目基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="科目名称")
    description: Optional[str] = Field(None, max_length=200, description="科目描述")


class SubjectCreate(SubjectBase):
    """创建科目的请求模型"""
    pass


class SubjectUpdate(SubjectBase):
    """更新科目的请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="科目名称")
    description: Optional[str] = None


class SubjectInDB(SubjectBase):
    """数据库中的科目模型"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class SubjectResponse(SubjectBase):
    """科目响应模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    knowledge_points_count: Optional[int] = 0

    class Config:
        orm_mode = True


class SubjectDetailResponse(SubjectResponse):
    """学科详情响应模型 - 包含更多信息如知识点数量"""
    questions_count: Optional[int] = 0
    
    class Config:
        orm_mode = True


class SubjectList(BaseModel):
    """科目列表响应模型"""
    subjects: List[SubjectResponse] = []

    class Config:
        from_attributes = True
