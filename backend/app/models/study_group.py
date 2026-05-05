from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import Base


class StudyGroup(Base):
    """学习小组 - 用户创建的学习组织"""
    __tablename__ = "study_groups"

    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject_ids = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    settings = Column(JSON, nullable=True)
    is_public = Column(String, default="public")

    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship("StudyGroupMember", back_populates="group", cascade="all, delete-orphan")

    def can_manage(self, user_id: int) -> bool:
        """只有创建者可以管理小组"""
        return self.owner_id == user_id


class StudyGroupMember(Base):
    """学习小组成员"""
    __tablename__ = "study_group_members"

    group_id = Column(Integer, ForeignKey("study_groups.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member")
    joined_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    nickname = Column(String(50), nullable=True)

    group = relationship("StudyGroup", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])