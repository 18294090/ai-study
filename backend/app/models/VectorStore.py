# 向量存储模型,使用pgvector存储向量数据
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.subject import Subject
from app.models.user import User
from pgvector.sqlalchemy import Vector
from typing import List, Optional
from pydantic import BaseModel

class DocumentChunk(Base):
    """
    文档切片向量存储模型
    用于存储文档切片的向量数据
    """
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)  # 切片内容
    embedding = Column(Vector(1024), nullable=False)  # 向量列
    title = Column(String(255), nullable=True)  # 可选的标题
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)  # 关联到 Book
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # 切片索引，用于排序
    # 关系
    book = relationship("Book", back_populates="chunks")

class DocumentChunkCreate(BaseModel):
    """
    文档切片创建模型
    """
    content: str
    embedding: List[float]
    title: Optional[str] = None
    book_id: int
    chunk_index: int
    user_id: int  # 添加用户ID字段

class DocumentChunkResponse(BaseModel):
    """
    文档切片响应模型
    """
    id: int
    content: str
    embedding: List[float]
    title: Optional[str] = None
    book_id: int
    chunk_index: int
    user_id: int  # 添加用户ID字段

class DocumentChunkUpdate(BaseModel):
    """
    文档切片更新模型
    """
    content: Optional[str] = None
    embedding: Optional[List[float]] = None
    title: Optional[str] = None
    chunk_index: Optional[int] = None
    user_id: Optional[int] = None  # 添加用户ID字段（可选更新）

