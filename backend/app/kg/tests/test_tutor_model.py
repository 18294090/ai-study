import pytest
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False)


class TutorSession(Base):
    __tablename__ = "tutor_sessions"

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

    session_id = Column(Integer, ForeignKey("tutor_sessions.id"))
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    hint_level = Column(Integer, nullable=True)
    state_at_time = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TutorSession", back_populates="messages")


class TutorHintTemplate(Base):
    __tablename__ = "tutor_hint_templates"

    concept_id = Column(String, nullable=False, index=True)
    hint_level = Column(Integer, nullable=False)
    template_text = Column(Text, nullable=False)


def test_tutor_session_creation():
    session = TutorSession(
        user_id=123,
        concept_id="slope",
        current_state="diagnose",
        target_concept_id="slope",
        turns_in_state=0
    )
    assert session.user_id == 123
    assert session.current_state == "diagnose"
    assert session.turns_in_state == 0


def test_tutor_message_creation():
    msg = TutorMessage(
        session_id=1,
        role="tutor",
        content="Let's explore slope",
        state_at_time="diagnose"
    )
    assert msg.role == "tutor"
    assert msg.state_at_time == "diagnose"


def test_hint_template_creation():
    template = TutorHintTemplate(
        concept_id="slope",
        hint_level=1,
        template_text="Think about what slope represents"
    )
    assert template.hint_level == 1
    assert "slope" in template.template_text