from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.undo_manager import UndoManager

router = APIRouter(prefix="/audit", tags=["audit"])

class AuditLogEntry(BaseModel):
    id: int
    agent_id: str
    session_id: str
    operation: str
    tool_name: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    result: str
    latency_ms: Optional[int]
    timestamp: datetime

class AuditLogResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    page: int
    page_size: int

class UndoRequest(BaseModel):
    session_id: str
    steps: int = 1

class UndoResponse(BaseModel):
    undone: int
    results: List[dict]

class UndoStackResponse(BaseModel):
    session_id: str
    operations: List[dict]

audit_service = AuditService()
undo_manager = UndoManager(audit_service)

@router.get("/logs", response_model=AuditLogResponse)
async def get_audit_logs(
    agent_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    tool_name: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    logs = await audit_service.get_logs(db, agent_id, session_id, tool_name, limit, offset)
    total = len(logs) + offset
    return AuditLogResponse(
        logs=[AuditLogEntry(**log.__dict__) for log in logs],
        total=total,
        page=offset // limit + 1,
        page_size=limit
    )

@router.get("/logs/{operation_id}", response_model=AuditLogEntry)
async def get_operation(
    operation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    log = await audit_service.get_operation(db, operation_id)
    if not log:
        raise HTTPException(status_code=404, detail="Operation not found")
    return AuditLogEntry(**log.__dict__)

@router.post("/undo", response_model=UndoResponse)
async def execute_undo(
    request: UndoRequest,
    agent_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    results = await undo_manager.undo(db, request.session_id, agent_id, request.steps)
    return UndoResponse(undone=len(results), results=results)

@router.get("/undo/stack/{session_id}", response_model=UndoStackResponse)
async def get_undo_stack(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ops = await undo_manager.get_stack(db, session_id)
    return UndoStackResponse(
        session_id=session_id,
        operations=[
            {
                "operation_id": op.operation_id,
                "tool_name": op.tool_name,
                "entity_type": op.entity_type,
                "entity_id": op.entity_id,
                "created_at": op.created_at.isoformat()
            }
            for op in ops
        ]
    )