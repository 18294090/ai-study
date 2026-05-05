from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

from app.mcp.kg_tools import ToolResponse


async def mastery_diagnose(user_id: int, concept_ids: List[int], agent_id: str, session_id: str) -> ToolResponse:
    """Run diagnostic test for concept mastery"""
    operation_id = str(uuid.uuid4())
    try:
        from app.services.bkt_service import BKTService, MasteryState
        from app.db.session import get_db

        service = BKTService()
        results = {}

        for concept_id in concept_ids:
            state = await service.get_mastery_state(user_id, concept_id)
            results[str(concept_id)] = {
                "p_know": state.p_know if state else 0.0,
                "attempts": state.attempts if state else 0,
                "correct_count": state.correct_count if state else 0,
            }

        return ToolResponse(
            success=True,
            data={"user_id": user_id, "concept_results": results},
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"mastery_diagnose failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def mastery_update(user_id: int, concept_id: int, is_correct: bool,
                          time_elapsed_seconds: Optional[float],
                          agent_id: str, session_id: str) -> ToolResponse:
    """Update mastery after student answer"""
    operation_id = str(uuid.uuid4())
    try:
        from app.services.bkt_service import BKTService
        from app.db.session import get_db

        service = BKTService()

        current_state = await service.get_mastery_state(user_id, concept_id)
        p_before = current_state.p_know if current_state else 0.3

        new_state = service.update(p_before, is_correct)

        if time_elapsed_seconds:
            hours = time_elapsed_seconds / 3600
            new_state = service.apply_forget(new_state.p_know, hours)

        await service.set_mastery_state(
            user_id=user_id,
            concept_id=concept_id,
            p_know=new_state.p_know,
            attempts=new_state.attempts,
            correct_count=new_state.correct_count
        )

        return ToolResponse(
            success=True,
            data={
                "user_id": user_id,
                "concept_id": concept_id,
                "p_before": p_before,
                "p_after": new_state.p_know,
                "attempts": new_state.attempts,
                "correct_count": new_state.correct_count,
            },
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"mastery_update failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def mastery_get(user_id: int, concept_id: Optional[int], agent_id: str, session_id: str) -> ToolResponse:
    """Get mastery state for user/concept"""
    operation_id = str(uuid.uuid4())
    try:
        from app.services.bkt_service import BKTService
        from app.models.mastery import MasteryRecord
        from app.db.session import get_db
        from sqlalchemy import select

        if concept_id is not None:
            service = BKTService()
            state = await service.get_mastery_state(user_id, concept_id)
            if state:
                return ToolResponse(
                    success=True,
                    data={
                        "user_id": user_id,
                        "concept_id": concept_id,
                        "p_know": state.p_know,
                        "attempts": state.attempts,
                        "correct_count": state.correct_count,
                    },
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )
            return ToolResponse(
                success=False,
                error=f"No mastery record for concept {concept_id}",
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        else:
            from app.db.session import async_session
            async with async_session() as db:
                stmt = select(MasteryRecord).filter(MasteryRecord.user_id == user_id)
                result = await db.execute(stmt)
                records = result.scalars().all()

                return ToolResponse(
                    success=True,
                    data={
                        "user_id": user_id,
                        "records": [
                            {
                                "concept_id": r.concept_id,
                                "p_know": r.p_know,
                                "attempts": r.attempts,
                                "correct_count": r.correct_count,
                                "last_updated": r.last_updated.isoformat() if r.last_updated else None,
                            }
                            for r in records
                        ]
                    },
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )
    except Exception as e:
        logger.error(f"mastery_get failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )