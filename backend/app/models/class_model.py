from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Table
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime

# 确保这个关联表存在且名称正确
class_student = Table(
    'class_student',
    Base.metadata,
    Column('class_id', Integer, ForeignKey('classes.id', ondelete="CASCADE"), primary_key=True),
    Column('student_id', Integer, ForeignKey('users.id', ondelete="CASCADE"), primary_key=True),
    extend_existing=True  # 修复语法错误，添加逗号并确保参数在括号内
)

class Class(Base):
    __tablename__ = "classes"    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)    
    # 明确指定foreign_keys参数
    teacher = relationship(
        "User", 
        foreign_keys=[teacher_id],
        back_populates="teaching_classes"  # 在User模型中需要对应的属性
    )    
    # 使用secondary表关联学生
    students = relationship(
        "User", 
        secondary=class_student,
        back_populates="enrolled_classes"  # 在User模型中需要对应的属性
    )
    
    # 添加缺失的assignments关系
    assignments = relationship(
        "Assignment",
        back_populates="class_",
        cascade="all, delete-orphan"
    )