from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class TutorSession(Base):
    __tablename__ = "tutor_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    concept_id = Column(String, nullable=False, index=True)
    current_state = Column(String, nullable=False, default="diagnose")
    turns_in_state = Column(Integer, default=0)
    target_concept_id = Column(String, nullable=False)
    misconception = Column(String, nullable=True)
    hint_level = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("TutorMessage", back_populates="session")


class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("tutor_sessions.id"), index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    hint_level = Column(Integer, nullable=True)
    state_at_time = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TutorSession", back_populates="messages")


class TutorHintTemplate(Base):
    __tablename__ = "tutor_hint_templates"

    id = Column(Integer, primary_key=True, index=True)
    concept_id = Column(String, nullable=False, index=True)
    hint_level = Column(Integer, nullable=False)
    template_text = Column(Text, nullable=False)