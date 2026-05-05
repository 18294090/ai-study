from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

from app.mcp.kg_tools import ToolResponse


async def expert_get_conflicts(status: Optional[str], min_severity: float,
                               limit: int, agent_id: str, session_id: str) -> ToolResponse:
    """Get conflict queue"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.expert_reviewer import KGConflict, ConflictQueue
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            query = db.query(KGConflict)

            if status:
                query = query.filter(KGConflict.status == status)
            query = query.filter(KGConflict.severity >= min_severity)

            conflicts = query.order_by(KGConflict.severity.desc()).limit(limit).all()

            return ToolResponse(
                success=True,
                data={
                    "conflicts": [
                        {
                            "id": c.id,
                            "conflict_type": c.conflict_type,
                            "severity": c.severity,
                            "entity_ids": c.entity_ids,
                            "statement_a": c.statement_a,
                            "statement_b": c.statement_b,
                            "source_a": c.source_a,
                            "source_b": c.source_b,
                            "context": c.context,
                            "status": c.status,
                            "created_at": c.created_at.isoformat() if c.created_at else None,
                            "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
                            "resolution": c.resolution,
                        }
                        for c in conflicts
                    ],
                    "count": len(conflicts),
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"expert_get_conflicts failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def expert_resolve(conflict_id: int, resolution: str, reasoning: str,
                         agent_id: str, session_id: str) -> ToolResponse:
    """Resolve a conflict"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.expert_reviewer import KGConflict
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            conflict = db.query(KGConflict).filter(KGConflict.id == conflict_id).first()
            if not conflict:
                return ToolResponse(
                    success=False,
                    error=f"Conflict {conflict_id} not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            conflict.status = "resolved"
            conflict.resolution = resolution
            conflict.resolver_id = None
            conflict.resolved_at = datetime.utcnow()

            db.commit()

            return ToolResponse(
                success=True,
                data={
                    "conflict_id": conflict_id,
                    "status": "resolved",
                    "resolution": resolution,
                    "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"expert_resolve failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def expert_submit_review(conflict_id: int, expert_id: int, recommendation: str,
                               confidence: float, reasoning: str,
                               agent_id: str, session_id: str) -> ToolResponse:
    """Submit expert review"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.expert_reviewer import ExpertReview, KGConflict
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            conflict = db.query(KGConflict).filter(KGConflict.id == conflict_id).first()
            if not conflict:
                return ToolResponse(
                    success=False,
                    error=f"Conflict {conflict_id} not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            review = ExpertReview(
                conflict_id=conflict_id,
                expert_id=expert_id,
                recommendation=recommendation,
                confidence=confidence,
                reasoning=reasoning,
                voted_at=datetime.utcnow(),
            )
            db.add(review)

            conflict.status = "reviewing"
            db.commit()
            db.refresh(review)

            return ToolResponse(
                success=True,
                data={
                    "review_id": review.id,
                    "conflict_id": conflict_id,
                    "expert_id": expert_id,
                    "recommendation": recommendation,
                    "confidence": confidence,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"expert_submit_review failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def expert_get_stats(agent_id: str, session_id: str) -> ToolResponse:
    """Get expert reviewer statistics"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.expert_reviewer import KGConflict, ExpertReview
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            total_conflicts = db.query(KGConflict).count()
            pending_conflicts = db.query(KGConflict).filter(KGConflict.status == "pending").count()
            reviewing_conflicts = db.query(KGConflict).filter(KGConflict.status == "reviewing").count()
            resolved_conflicts = db.query(KGConflict).filter(KGConflict.status == "resolved").count()

            total_reviews = db.query(ExpertReview).count()

            avg_severity = db.query(KGConflict).filter(
                KGConflict.status == "resolved"
            ).avg(KGConflict.severity)

            return ToolResponse(
                success=True,
                data={
                    "total_conflicts": total_conflicts,
                    "pending_conflicts": pending_conflicts,
                    "reviewing_conflicts": reviewing_conflicts,
                    "resolved_conflicts": resolved_conflicts,
                    "total_reviews": total_reviews,
                    "avg_severity_resolved": float(avg_severity) if avg_severity else 0.0,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"expert_get_stats failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )