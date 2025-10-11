from app.crud import subject
from sqlalchemy import Column, Integer, String, Table, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from app.models.base import Base
import datetime  # 保留此导入，使用 datetime.utcnow

# 用户-学科关联表
user_subject = Table(
    'user_subject',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    Column('subject_id', Integer, ForeignKey('subjects.id', ondelete="CASCADE"), primary_key=True),
    extend_existing=True  # 添加此参数以允许表被重新定义    
    )

# 添加 question_tags 关联表定义
question_tags = Table(
    'question_tags',
    Base.metadata,
    Column('question_id', Integer, ForeignKey('questions.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)

class Subject(Base):
    """科目模型"""
    __tablename__ = "subjects"    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, comment="科目名称")
    description = Column(Text, nullable=True, comment="科目描述")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  
    teachers = relationship("User", secondary=user_subject, back_populates="subjects")
    # 与用户的关系
    user = relationship("User", back_populates="subjects")    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    questions = relationship("Question", back_populates="subject", cascade="all, delete-orphan")
    books=relationship("Book", back_populates="subject")
    tags = relationship("Tag", back_populates="subject", cascade="all, delete-orphan")

class Tag(Base):
    """标签模型"""
    __tablename__ = "tags"
    __table_args__ = {'extend_existing': True}  # 添加此行以允许表重新定义
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, comment="标签名称")
    description = Column(Text, nullable=True, comment="标签描述")
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True, comment="所属科目ID")
    subject = relationship("Subject", back_populates="tags")
    # 关系：创建该标签的用户
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    creator = relationship("User", back_populates="created_tags")
    # 关系：标签关联的问题
    questions = relationship(
        "Question",
        secondary=question_tags,  # 改为使用表对象
        back_populates="tags"
    )