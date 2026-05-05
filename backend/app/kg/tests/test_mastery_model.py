import sys
sys.path.insert(0, '/home/zh/ai-study/backend')

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase

import pytest


class Base(DeclarativeBase):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False)


class MasteryRecord(Base):
    __tablename__ = "mastery_records"

    user_id: int = Column(Integer, nullable=False, index=True)
    concept_id: str = Column(String, nullable=False, index=True)
    p_know: float = Column(Float, nullable=False, default=0.3)
    attempts: int = Column(Integer, nullable=False, default=0)
    correct_count: int = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('user_id', 'concept_id', name='uq_user_concept'),
    )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "concept_id": self.concept_id,
            "p_know": self.p_know,
            "attempts": self.attempts,
            "correct_count": self.correct_count,
            "last_updated": str(self.last_updated) if self.last_updated else None,
        }


class AnswerLog(Base):
    __tablename__ = "answer_logs"

    user_id: int = Column(Integer, nullable=False, index=True)
    concept_id: str = Column(String, nullable=False, index=True)
    question_id: int = Column(Integer, nullable=False)
    is_correct: bool = Column(Boolean, nullable=False)
    bkt_p_before: float = Column(Float, nullable=False)
    bkt_p_after: float = Column(Float, nullable=False)


class DiagnosticResult(Base):
    __tablename__ = "diagnostic_results"

    user_id: int = Column(Integer, nullable=False, index=True)
    concept_id: str = Column(String, nullable=False, index=True)
    initial_p: float = Column(Float, nullable=False)
    questions_answered: int = Column(Integer, nullable=False, default=0)
    questions_correct: int = Column(Integer, nullable=False, default=0)


def test_mastery_record_creation():
    record = MasteryRecord(
        user_id=123,
        concept_id="concept_001",
        p_know=0.75,
        attempts=5,
        correct_count=4
    )
    assert record.user_id == 123
    assert record.concept_id == "concept_001"
    assert record.p_know == 0.75
    assert record.attempts == 5
    assert record.correct_count == 4


def test_mastery_record_to_dict():
    record = MasteryRecord(
        user_id=123,
        concept_id="concept_001",
        p_know=0.75,
        attempts=5,
        correct_count=4
    )
    d = record.to_dict()
    assert d["user_id"] == 123
    assert d["concept_id"] == "concept_001"
    assert d["p_know"] == 0.75


def test_answer_log_creation():
    log = AnswerLog(
        user_id=123,
        concept_id="concept_001",
        question_id=1001,
        is_correct=True,
        bkt_p_before=0.6,
        bkt_p_after=0.8
    )
    assert log.is_correct is True
    assert log.bkt_p_after > log.bkt_p_before


def test_diagnostic_result_creation():
    diag = DiagnosticResult(
        user_id=123,
        concept_id="concept_001",
        initial_p=0.65,
        questions_answered=5,
        questions_correct=3
    )
    assert diag.initial_p == 0.65
    assert diag.questions_correct == 3