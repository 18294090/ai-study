from pydantic import BaseModel
from typing import Optional

class KnowledgePointBase(BaseModel):
    name: str
    description: Optional[str] = None    

class KnowledgePointCreate(KnowledgePointBase):
    id: int  # 添加 id 字段

class KnowledgePointUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class KnowledgePointResponse(BaseModel):
    # 调整为字典，匹配 Neo4j 返回
    id: int
    name: str
    description: Optional[str] = None
    # 添加其他 Neo4j 字段
    difficulty: Optional[int] = None
    subject_id: Optional[int] = None
    creator_id: Optional[int] = None
