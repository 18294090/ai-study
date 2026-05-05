from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, JSON, Index
from app.models.base import Base


class UndoOperation(Base):
    __tablename__ = "undo_operations"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    operation_id = Column(String, nullable=False, unique=True)
    tool_name = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    rollback_data = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_session_operation_id', 'session_id', 'operation_id'),
    )
