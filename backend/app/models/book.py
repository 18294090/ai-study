from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base import Base
from typing import Optional


class Book(Base):
    """
    书籍/文档模型
    """
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)  # 标题
    content = Column(Text, nullable=True)  # 内容（可选）
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    # 关系    
    subject = relationship("Subject", back_populates="books")
    chunks = relationship("DocumentChunk", back_populates="book")  # 关联切片


