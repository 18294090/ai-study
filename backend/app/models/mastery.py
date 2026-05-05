from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, UniqueConstraint
from app.models.base import Base


class MasteryRecord(Base):
    __tablename__ = "mastery_records"

    user_id: int = Column(Integer, nullable=False, index=True)
    concept_id: str = Column(String, nullable=False, index=True)
    p_know: float = Column(Float, nullable=False, default=0.3)
    attempts: int = Column(Integer, nullable=False, default=0)
    correct_count: int = Column(Integer, nullable=False, default=0)
    last_updated: datetime = Column(DateTime(timezone=True), nullable=True)

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