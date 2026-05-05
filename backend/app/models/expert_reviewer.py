from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.models.base import Base


class ConflictType(str, Base):
    CONTRADICTION = "contradiction"
    TEMPORAL = "temporal"
    GRANULARITY = "granularity"
    NAMING = "naming"


class ConflictStatus(str, Base):
    PENDING = "pending"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class RecommendationType(str, Base):
    ACCEPT_A = "accept_a"
    ACCEPT_B = "accept_b"
    MERGE = "merge"
    REJECT = "reject"


class KGConflict(Base):
    __tablename__ = "kg_conflicts"

    id = Column(Integer, primary_key=True)
    conflict_type = Column(String, nullable=False)
    severity = Column(Float, nullable=False)
    entity_ids = Column(String, nullable=False)
    statement_a = Column(Text, nullable=False)
    statement_b = Column(Text, nullable=False)
    source_a = Column(String, nullable=False)
    source_b = Column(String, nullable=False)
    context = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution = Column(Text, nullable=True)
    resolver_id = Column(Integer, nullable=True)
    metadata = Column(String, nullable=True)


class ExpertReview(Base):
    __tablename__ = "expert_reviews"

    id = Column(Integer, primary_key=True)
    conflict_id = Column(Integer, ForeignKey("kg_conflicts.id"), nullable=False, index=True)
    expert_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recommendation = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=False)
    voted_at = Column(DateTime(timezone=True), nullable=False)


class ConflictQueue(Base):
    __tablename__ = "kg_conflict_queue"

    id = Column(Integer, primary_key=True)
    priority = Column(Integer, nullable=False, default=1)
    conflict_id = Column(Integer, ForeignKey("kg_conflicts.id"), nullable=False, index=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    due_date = Column(DateTime(timezone=True), nullable=False)
    notifications_sent = Column(Integer, nullable=False, default=0)