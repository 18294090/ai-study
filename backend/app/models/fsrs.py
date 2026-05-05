from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


class CardState(str, Enum):
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    RELEARNING = "relearning"


class ReviewRating(int, Enum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


class FSRSCard(Base):
    __tablename__ = "fsrs_cards"

    user_id: int = Column(Integer, nullable=False, index=True)
    concept_id: int = Column(Integer, nullable=False, index=True)
    state: str = Column(String, nullable=False, default=CardState.NEW.value)
    stability: float = Column(Float, nullable=False, default=0.0)
    difficulty: float = Column(Float, nullable=False, default=0.3)
    retrievability: float = Column(Float, nullable=True)
    interval: float = Column(Float, nullable=False, default=0.0)
    due: datetime = Column(DateTime(timezone=True), nullable=True)
    last_review: datetime = Column(DateTime(timezone=True), nullable=True)
    last_result: str = Column(String, nullable=True)
    reps: int = Column(Integer, nullable=False, default=0)
    lapses: int = Column(Integer, nullable=False, default=0)
    metadata_json: dict = Column(JSON, nullable=True)

    review_logs = relationship("FSRSReviewLog", back_populates="card")


class FSRSReviewLog(Base):
    __tablename__ = "fsrs_review_logs"

    card_id: int = Column(Integer, ForeignKey("fsrs_cards.id"), nullable=False, index=True)
    user_id: int = Column(Integer, nullable=False, index=True)
    reviewed_at: datetime = Column(DateTime(timezone=True), nullable=False)
    rating: int = Column(Integer, nullable=False)
    response_time: float = Column(Float, nullable=False)
    stability_delta: float = Column(Float, nullable=False)
    new_interval: float = Column(Float, nullable=False)
    new_stability: float = Column(Float, nullable=False)
    retention: float = Column(Float, nullable=False)

    card = relationship("FSRSCard", back_populates="review_logs")
