from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, JSON, Index
from app.models.base import Base


class AgentOperationLog(Base):
    __tablename__ = "agent_operation_logs"

    id = Column(Integer, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    operation = Column(String, nullable=False)
    tool_name = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    result = Column(String, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_agent_session', 'agent_id', 'session_id'),
        Index('ix_tool_name', 'tool_name'),
    )
