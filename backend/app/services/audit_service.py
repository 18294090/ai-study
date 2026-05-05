from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.audit import AgentOperationLog

class AuditService:
    """Service for recording and querying audit logs"""

    async def log_operation(
        self,
        db: AsyncSession,
        agent_id: str,
        session_id: str,
        operation: str,
        tool_name: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
        result: str = "success",
        latency_ms: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> AgentOperationLog:
        """Record an operation to the audit log"""
        log = AgentOperationLog(
            agent_id=agent_id,
            session_id=session_id,
            operation=operation,
            tool_name=tool_name,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            result=result,
            latency_ms=latency_ms,
            metadata=metadata,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    async def get_logs(
        self,
        db: AsyncSession,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AgentOperationLog]:
        """Query audit logs with filters"""
        stmt = select(AgentOperationLog)

        if agent_id:
            stmt = stmt.filter(AgentOperationLog.agent_id == agent_id)
        if session_id:
            stmt = stmt.filter(AgentOperationLog.session_id == session_id)
        if tool_name:
            stmt = stmt.filter(AgentOperationLog.tool_name == tool_name)

        stmt = stmt.order_by(desc(AgentOperationLog.timestamp))
        stmt = stmt.offset(offset).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_operation(self, db: AsyncSession, operation_id: int) -> Optional[AgentOperationLog]:
        """Get single operation by ID"""
        result = await db.execute(
            select(AgentOperationLog).filter(AgentOperationLog.id == operation_id)
        )
        return result.scalar_one_or_none()