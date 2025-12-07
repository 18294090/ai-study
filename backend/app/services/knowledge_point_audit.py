"""Audit logging helpers for knowledge point lifecycle."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint, KnowledgePointAuditLog


def _snapshot(kp: KnowledgePoint) -> Dict[str, Any]:
    return {
        "id": kp.id,
        "code": kp.code,
        "slug": kp.slug,
        "name": kp.name,
        "subject_id": kp.subject_id,
        "status": kp.status.value if hasattr(kp.status, "value") else kp.status,
        "version": kp.version,
    }


async def record_audit_event(
    db: AsyncSession,
    knowledge_point: KnowledgePoint,
    stage: str,
    reviewer_id: str,
    reviewer_name: str,
    status: str = "pending",
    comment: Optional[str] = None,
) -> KnowledgePointAuditLog:
    """Persist an audit log row for the provided knowledge point."""
    log = KnowledgePointAuditLog(
        knowledge_point_id=knowledge_point.id,
        stage=stage,
        reviewer_id=reviewer_id,
        reviewer_name=reviewer_name,
        status=status,
        comment=comment,
        reviewed_data=_snapshot(knowledge_point),
    )
    db.add(log)
    await db.flush()
    return log


__all__ = ["record_audit_event"]
