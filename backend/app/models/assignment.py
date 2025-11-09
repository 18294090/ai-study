# app/models/assignment.py
"""
作业与提交记录相关模型
- Assignment: 用户创建的作业/试卷
- UserAssignment: 用户完成作业的记录
- UserAnswer: 用户对单个问题的回答
"""
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    JSON,
    Enum as SQLAlchemyEnum,
    Text,
    ForeignKey,
    Table,
    Column,
    DateTime,
    Float,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.question import Question
    from app.models.class_model import Class
    from app.models.knowledge import KnowledgePoint

# 关联表：作业和问题 (多对多)
assignment_question_table = Table(
    "assignment_question",
    Base.metadata,
    Column("assignment_id", ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True),
    Column("question_id", ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
)

class AssignmentStatus(str, Enum):
    """作业状态"""
    DRAFT = "draft"  # 草稿
    PUBLISHED = "published"  # 已发布
    CLOSED = "closed"  # 已截止

class UserAssignmentStatus(str, Enum):
    """用户作业完成状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADED = "graded"

def _load_knowledge_point():
    from app.models.knowledge import KnowledgePoint
    return KnowledgePoint

class Assignment(Base):
    """作业/试卷模型"""
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), comment="作业标题")
    description: Mapped[Optional[str]] = mapped_column(Text, comment="作业描述")
    instructions: Mapped[Optional[str]] = mapped_column(Text, comment="作业要求")
    due_days: Mapped[Optional[int]] = mapped_column(Integer, comment="建议完成天数")
    evaluation_criteria: Mapped[Optional[dict]] = mapped_column(JSON, comment="评估标准")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="截止日期")
    status: Mapped[AssignmentStatus] = mapped_column(
        SQLAlchemyEnum(AssignmentStatus, name="assignment_status_enum"),
        default=AssignmentStatus.DRAFT,
        comment="作业状态"
    )

    # 关系
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="创建者ID")
    creator: Mapped["User"] = relationship(back_populates="created_assignments")

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), comment="所属班级ID")
    class_: Mapped["Class"] = relationship(back_populates="assignments")

    questions: Mapped[List["Question"]] = relationship(
        "Question",
        secondary=assignment_question_table,
        back_populates="assignments"
    )

    user_assignments: Mapped[List["UserAssignment"]] = relationship(
        "UserAssignment",
        back_populates="assignment",
        cascade="all, delete-orphan"
    )

    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), comment="知识点ID")
    knowledge_point = relationship(_load_knowledge_point, back_populates="assignments")

    def __repr__(self) -> str:
        return f"<Assignment(id={self.id}, title='{self.title}')>"


class UserAssignment(Base):
    """用户作业记录模型"""
    __tablename__ = "user_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # 关系
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), comment="用户ID")
    user: Mapped["User"] = relationship(back_populates="user_assignments")

    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), comment="作业ID")
    assignment: Mapped["Assignment"] = relationship(back_populates="user_assignments")

    # 状态与分数
    status: Mapped[UserAssignmentStatus] = mapped_column(
        SQLAlchemyEnum(UserAssignmentStatus, name="user_assignment_status_enum"),
        default=UserAssignmentStatus.NOT_STARTED,
        comment="完成状态"
    )
    score: Mapped[Optional[float]] = mapped_column(Float, comment="得分")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="开始时间")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="提交时间")

    # 答案
    answers: Mapped[List["UserAnswer"]] = relationship(
        "UserAnswer",
        back_populates="user_assignment",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UserAssignment(id={self.id}, user_id={self.user_id}, assignment_id={self.assignment_id})>"


class UserAnswer(Base):
    """用户答案模型"""
    __tablename__ = "user_answers"

    id = Column(Integer, primary_key=True, index=True)

    # 关系
    user_assignment_id: Mapped[int] = mapped_column(ForeignKey("user_assignments.id", ondelete="CASCADE"), comment="用户作业记录ID")
    user_assignment: Mapped["UserAssignment"] = relationship(back_populates="answers")

    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), comment="问题ID")
    question: Mapped["Question"] = relationship("Question", back_populates="user_answers")

    # 答案内容
    answer_content: Mapped[dict] = mapped_column(JSON, comment="用户答案内容")
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, comment="是否正确")
    score: Mapped[Optional[float]] = mapped_column(Float, comment="该题得分")

    def __repr__(self) -> str:
        return f"<UserAnswer(id={self.id}, user_assignment_id={self.user_assignment_id}, question_id={self.question_id})>"


