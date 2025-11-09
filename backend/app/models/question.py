#问题模型，题库，存储学生学科练习题，问题标题，类型，学科，内容，难度，标签等信息
from typing import List, Optional, TYPE_CHECKING
from enum import Enum
from sqlalchemy import Column, String, Integer, JSON, Enum as SQLAlchemyEnum, Text, ForeignKey, DateTime, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
import datetime
from app.models.subject import Tag, question_tags  # 添加导入以使用 subject.py 中的 Tag 类和 question_tags

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.assignment import Assignment

class QuestionType(str, Enum):
    """问题类型"""
    SINGLE_CHOICE = "single_choice"    # 单选题（包括判断题）
    MULTIPLE_CHOICE = "multiple_choice" # 多选题
    FILL_IN_BLANK = "fill_in_blank"    # 填空题
    SHORT_ANSWER = "short_answer"      # 简答题

    @classmethod
    def get_display_name(cls, value: str) -> str:
        """获取显示名称"""
        display_names = {
            cls.SINGLE_CHOICE.value: "单选题",
            cls.MULTIPLE_CHOICE.value: "多选题",
            cls.FILL_IN_BLANK.value: "填空题",
            cls.SHORT_ANSWER.value: "简答题"
        }
        return display_names.get(value, value)

class QuestionStatus(str, Enum):
    """问题状态"""
    DRAFT = "draft"  # 草稿
    ACTIVE = "active"  # 已发布
    DEPRECATED = "deprecated"  # 已废弃

# 题目-知识点 关联表
question_knowledge_point = Table(
    'question_knowledge_point',
    Base.metadata,
    Column('question_id', Integer, ForeignKey('questions.id'), primary_key=True),
    Column('knowledge_point_id', Integer, ForeignKey('knowledge_points.id'), primary_key=True)
)

class ContentFormat(str, Enum):
    """内容格式类型"""
    PLAIN = "plain"      # 纯文本
    HTML = "html"        # HTML富文本
    MARKDOWN = "markdown"  # Markdown格式

class Question(Base):
    """问题模型"""
    __tablename__ = "questions"
    # id, created_at, updated_at 字段从 Base 类继承
    # --- 核心信息 ---
    id = Column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), comment="问题标题")
    type: Mapped[QuestionType] = mapped_column(SQLAlchemyEnum(QuestionType, name="question_type_enum"), comment="问题类型")
    content: Mapped[str] = mapped_column(Text, comment="问题内容（题干）")
    content_format: Mapped[ContentFormat] = mapped_column(
        SQLAlchemyEnum(ContentFormat, name="content_format_enum"), 
        default=ContentFormat.HTML, 
        comment="内容格式类型"
    )
    options: Mapped[Optional[dict]] = mapped_column(JSON, comment="选项（针对选择题，支持富文本）")    
    # 新增字段：标识选项是否为富文本格式
    options_format: Mapped[ContentFormat] = mapped_column(
        SQLAlchemyEnum(ContentFormat, name="options_format_enum"), 
        default=ContentFormat.HTML, 
        comment="选项内容格式"
    )    
    answer: Mapped[dict] = mapped_column(JSON, comment="正确答案")
    explanation: Mapped[Optional[str]] = mapped_column(Text, comment="答案解析")
    explanation_format: Mapped[ContentFormat] = mapped_column(
        SQLAlchemyEnum(ContentFormat, name="explanation_format_enum"), 
        default=ContentFormat.HTML, 
        comment="答案解析格式"
    )
    picture: Mapped[Optional[str]] = mapped_column(String(255), comment="题目图片")
    # --- 教学与分析信息 ---
    difficulty: Mapped[int] = mapped_column(Integer, comment="难度等级")
    tags: Mapped[List[str]] = mapped_column(JSON, comment="标签列表")
    subject_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subjects.id"), comment="所属科目ID")
    subject = relationship("Subject", back_populates="questions")
    # --- 管理与追踪信息 ---
    source: Mapped[Optional[str]] = mapped_column(String(255), comment="题目来源")
    status: Mapped[QuestionStatus] = mapped_column(SQLAlchemyEnum(QuestionStatus, name="question_status_enum"), default=QuestionStatus.DRAFT, comment="题目状态")
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), comment="创建者ID")
    author = relationship("User", back_populates="questions")    
    # 关系：问题所属的作业
    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment",
        secondary="assignment_question", # 使用表名字符串
        back_populates="questions"
    )
    # 关系：学生对该问题的回答
    user_answers = relationship(
        "UserAnswer", back_populates="question"
    )
    # 关系：问题关联的知识点
    knowledge_points: Mapped[List["KnowledgePoint"]] = relationship(
        "KnowledgePoint",
        secondary=question_knowledge_point,
        lazy="selectin",  # 使用selectin加载策略
        back_populates="questions",
        info={"description": "关联知识点列表"}
    )
    # 关系：问题的评论
    comments = relationship("QuestionComment", back_populates="question", cascade="all, delete-orphan")
    # 关系：问题的标签
    tags = relationship("Tag", secondary=question_tags, back_populates="questions", lazy="selectin")  # 添加 lazy="selectin" 以预加载标签
    def __repr__(self) -> str:
        return f"<Question(id={self.id}, title='{self.title}')>"

class QuestionComment(Base):
    """问题评论模型"""
    __tablename__ = "question_comments"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False, comment="评论内容")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="创建时间")
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, comment="问题ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    # 关系：评论所属的问题
    question = relationship("Question", back_populates="comments")
    # 关系：评论的作者
    user = relationship("User", back_populates="comments")