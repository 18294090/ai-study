# 向量存储模型,使用pgvector存储向量数据
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.subject import Subject
from app.models.user import User
from pgvector.sqlalchemy import Vector
from typing import List, Optional
from pydantic import BaseModel

class QuestionVector(Base):
    """
    试题向量存储模型
    用于存储试题的向量数据，支持语义搜索
    """
    __tablename__ = "question_vectors"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)  # 试题内容
    embedding = Column(Vector(1024), nullable=False)  # 向量列，使用bge-m3模型
    title = Column(String(255), nullable=True)  # 试题标题
    question_type = Column(String(50), nullable=True)  # 试题类型
    difficulty = Column(Integer, nullable=True)  # 难度等级
    source = Column(String(255), nullable=True)  # 来源
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)  # 学科ID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 用户ID
    tags = Column(String(500), nullable=True)  # 标签，JSON字符串格式
    created_at = Column(String(50), nullable=True)  # 创建时间戳
    # 关系
    subject = relationship("Subject", backref="question_vectors")
    user = relationship("User", backref="question_vectors")

class QuestionVectorCreate(BaseModel):
    """
    试题向量创建模型
    """
    content: str
    embedding: List[float]
    title: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[int] = None
    source: Optional[str] = None
    subject_id: Optional[int] = None
    user_id: int
    tags: Optional[str] = None

class QuestionVectorResponse(BaseModel):
    """
    试题向量响应模型
    """
    id: int
    content: str
    embedding: List[float]
    title: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[int] = None
    source: Optional[str] = None
    subject_id: Optional[int] = None
    user_id: int
    tags: Optional[str] = None
    created_at: Optional[str] = None

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

