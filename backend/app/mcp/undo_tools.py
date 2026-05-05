from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

from app.mcp.kg_tools import ToolResponse


async def undo(session_id: str, agent_id: str, steps: int = 1) -> ToolResponse:
    """Undo last N operations"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.undo import UndoOperation
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            operations = db.query(UndoOperation).filter(
                UndoOperation.session_id == session_id,
                UndoOperation.status == "completed",
            ).order_by(UndoOperation.created_at.desc()).limit(steps).all()

            if len(operations) < steps:
                return ToolResponse(
                    success=False,
                    error=f"Only {len(operations)} operations found to undo, requested {steps}",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            undone = []
            for op in operations:
                op.status = "undone"
                op.completed_at = datetime.utcnow()
                undone.append({
                    "operation_id": op.operation_id,
                    "tool_name": op.tool_name,
                    "entity_type": op.entity_type,
                    "entity_id": op.entity_id,
                })

            db.commit()

            return ToolResponse(
                success=True,
                data={
                    "undone_count": len(undone),
                    "operations": undone,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"undo failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def get_undo_stack(session_id: str, agent_id: str) -> ToolResponse:
    """Get current undo stack for session"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.undo import UndoOperation
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            operations = db.query(UndoOperation).filter(
                UndoOperation.session_id == session_id,
            ).order_by(UndoOperation.created_at.desc()).all()

            return ToolResponse(
                success=True,
                data={
                    "session_id": session_id,
                    "operations": [
                        {
                            "id": op.id,
                            "operation_id": op.operation_id,
                            "tool_name": op.tool_name,
                            "operation_type": op.operation_type,
                            "entity_type": op.entity_type,
                            "entity_id": op.entity_id,
                            "status": op.status,
                            "created_at": op.created_at.isoformat() if op.created_at else None,
                            "completed_at": op.completed_at.isoformat() if op.completed_at else None,
                        }
                        for op in operations
                    ],
                    "count": len(operations),
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"get_undo_stack failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )