from pydantic import BaseModel, Field
from typing import Optional


class KnowledgePointBase(BaseModel):
    name: str = Field(..., description="知识点名称")
    description: Optional[str] = Field(None, description="知识点描述")
    difficulty: Optional[int] = Field(3, ge=1, le=5, description="难度等级(1-5)，默认3")


class KnowledgePointCreate(KnowledgePointBase):
    # id 由后端创建(数据库自增)，不从客户端获取
    parent_id: Optional[int] = Field(None, description="父知识点ID，可为空表示根节点")


class KnowledgePointUpdate(BaseModel):
    name: Optional[str] = Field(None, description="知识点名称")
    description: Optional[str] = Field(None, description="知识点描述")
    difficulty: Optional[int] = Field(None, ge=1, le=5, description="难度等级(1-5)")


class KnowledgePointResponse(BaseModel):
    # 兼容 Neo4j 返回，同时补充必要字段
    id: int
    name: str
    description: Optional[str] = None
    difficulty: Optional[int] = None
    subject_id: Optional[int] = None
    creator_id: Optional[int] = None
