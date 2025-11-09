# 知识点模型
from importlib import resources
import resource
from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base import Base
from typing import Optional
from app.models.question import question_knowledge_point

class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id"), nullable=False)
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    # 关系
    creator = relationship("User", back_populates="created_knowledge_points")
    subject = relationship("Subject", back_populates="knowledge_points")
    # 添加缺失的relationship
    assignments = relationship("Assignment", back_populates="knowledge_point", cascade="all, delete-orphan")    
    # 添加缺失的relationship
    questions = relationship("Question", secondary=question_knowledge_point, back_populates="knowledge_points")
    resources = relationship("Resource", back_populates="knowledge_point", cascade="all, delete-orphan")

