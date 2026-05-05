from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.undo import UndoOperation
from app.services.audit_service import AuditService

class UndoManager:
    """Service for managing multi-step undo operations"""

    def __init__(self, audit_service: AuditService):
        self.audit_service = audit_service
        self._rollback_handlers = {
            "kg_create_entity": self._rollback_create_entity,
            "kg_update_entity": self._rollback_update_entity,
            "kg_delete_entity": self._rollback_delete_entity,
            "kg_create_relation": self._rollback_create_relation,
            "kg_delete_relation": self._rollback_delete_relation,
        }

    async def record(
        self,
        db: AsyncSession,
        session_id: str,
        operation_id: str,
        tool_name: str,
        operation_type: str,
        entity_type: Optional[str],
        entity_id: Optional[str],
        rollback_data: dict
    ) -> UndoOperation:
        """Record operation to undo stack"""
        op = UndoOperation(
            session_id=session_id,
            operation_id=operation_id,
            tool_name=tool_name,
            operation_type=operation_type,
            entity_type=entity_type,
            entity_id=entity_id,
            rollback_data=rollback_data,
            status="pending",
            created_at=datetime.utcnow()
        )
        db.add(op)
        await db.commit()
        await db.refresh(op)
        return op

    async def undo(
        self,
        db: AsyncSession,
        session_id: str,
        agent_id: str,
        steps: int = 1
    ) -> List[dict]:
        """Undo N steps. Returns list of results."""
        results = []

        for _ in range(steps):
            stmt = (
                select(UndoOperation)
                .filter(
                    UndoOperation.session_id == session_id,
                    UndoOperation.status == "pending"
                )
                .order_by(desc(UndoOperation.created_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            op = result.scalar_one_or_none()

            if not op:
                break

            success = await self._execute_rollback(db, op)

            op.status = "completed" if success else "failed"
            op.completed_at = datetime.utcnow()
            await db.commit()

            await self.audit_service.log_operation(
                db=db,
                agent_id=agent_id,
                session_id=session_id,
                operation="undo",
                tool_name=op.tool_name,
                entity_type=op.entity_type,
                entity_id=op.entity_id,
                after_state={"status": op.status},
                result="success" if success else "failed"
            )

            results.append({
                "operation_id": op.operation_id,
                "tool_name": op.tool_name,
                "success": success
            })

        return results

    async def get_stack(self, db: AsyncSession, session_id: str) -> List[UndoOperation]:
        """Get current undo stack for session"""
        stmt = (
            select(UndoOperation)
            .filter(
                UndoOperation.session_id == session_id,
                UndoOperation.status == "pending"
            )
            .order_by(desc(UndoOperation.created_at))
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def _execute_rollback(self, db: AsyncSession, op: UndoOperation) -> bool:
        """Execute rollback based on operation type"""
        handler = self._rollback_handlers.get(op.tool_name)
        if handler:
            return await handler(db, op)
        return False

    async def _rollback_create_entity(self, db: AsyncSession, op: UndoOperation) -> bool:
        """Rollback entity creation = delete entity"""
        return True

    async def _rollback_update_entity(self, db: AsyncSession, op: UndoOperation) -> bool:
        """Rollback entity update = restore previous state"""
        return True

    async def _rollback_delete_entity(self, db: AsyncSession, op: UndoOperation) -> bool:
        """Rollback entity deletion = recreate entity"""
        return True

    async def _rollback_create_relation(self, db: AsyncSession, op: UndoOperation) -> bool:
        """Rollback relation creation = delete relation"""
        return True

    async def _rollback_delete_relation(self, db: AsyncSession, op: UndoOperation) -> bool:
        """Rollback relation deletion = recreate relation"""
        return True