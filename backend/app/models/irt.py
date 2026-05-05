from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, JSON
from app.models.base import Base


class IRTItemParams(Base):
    __tablename__ = "irt_item_params"

    question_id: int = Column(Integer, nullable=False, index=True)
    model_type: str = Column(String(10), nullable=False)
    a: float = Column(Float, nullable=False)
    b: float = Column(Float, nullable=False)
    c: float = Column(Float, nullable=False, default=0)
    info: float = Column(Float, nullable=False, default=0)
    sample_size: int = Column(Integer, nullable=False, default=0)
    calibrated_at: datetime = Column(DateTime(timezone=True), nullable=True)
    status: str = Column(String(20), nullable=False, default="calibrating")
    metadata_json: dict = Column(JSON, nullable=True)


class IRTAbilityEstimate(Base):
    __tablename__ = "irt_ability_estimates"

    user_id: int = Column(Integer, nullable=False, index=True)
    subject_id: int = Column(Integer, nullable=False, index=True)
    theta: float = Column(Float, nullable=False)
    se: float = Column(Float, nullable=False)
    method: str = Column(String(10), nullable=False)
    based_on: int = Column(Integer, nullable=False, default=0)
    estimated_at: datetime = Column(DateTime(timezone=True), nullable=False)


class IRTCalibrationSession(Base):
    __tablename__ = "irt_calibration_sessions"

    subject_id: int = Column(Integer, nullable=False, index=True)
    method: str = Column(String(20), nullable=False)
    iterations: int = Column(Integer, nullable=False, default=0)
    converged: bool = Column(Boolean, nullable=False, default=False)
    final_loglik: float = Column(Float, nullable=False, default=0)


class ResponseRecord(Base):
    __tablename__ = "irt_response_records"

    question_id: int = Column(Integer, nullable=False, index=True)
    user_id: int = Column(Integer, nullable=False, index=True)
    correct: bool = Column(Boolean, nullable=False)
    response_time: float = Column(Float, nullable=False)
    attempt: int = Column(Integer, nullable=False, default=1)
    recorded_at: datetime = Column(DateTime(timezone=True), nullable=False)
