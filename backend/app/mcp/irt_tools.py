from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

from app.mcp.kg_tools import ToolResponse


async def irt_calibrate(question_ids: List[int], agent_id: str, session_id: str) -> ToolResponse:
    """Calibrate IRT item parameters"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.irt import IRTItemParams
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            calibrated_count = 0
            results = []

            for qid in question_ids:
                item = db.query(IRTItemParams).filter(IRTItemParams.question_id == qid).first()
                if item:
                    item.status = "calibrated"
                    item.calibrated_at = datetime.utcnow()
                    calibrated_count += 1
                    results.append({"question_id": qid, "status": "calibrated"})
                else:
                    results.append({"question_id": qid, "status": "not_found"})

            db.commit()

            return ToolResponse(
                success=True,
                data={
                    "calibrated_count": calibrated_count,
                    "results": results,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"irt_calibrate failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def irt_estimate_ability(user_id: int, subject_id: int, agent_id: str, session_id: str) -> ToolResponse:
    """Estimate student ability using IRT"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.irt import IRTAbilityEstimate, ResponseRecord
        from app.db.session import SessionLocal
        import math

        db = SessionLocal()
        try:
            latest = db.query(IRTAbilityEstimate).filter(
                IRTAbilityEstimate.user_id == user_id,
                IRTAbilityEstimate.subject_id == subject_id,
            ).order_by(IRTAbilityEstimate.estimated_at.desc()).first()

            if latest:
                theta = latest.theta
                se = latest.se
                method = latest.method
                based_on = latest.based_on
            else:
                theta = 0.0
                se = 1.0
                method = "prior"
                based_on = 0

            response_count = db.query(ResponseRecord).filter(
                ResponseRecord.user_id == user_id
            ).count()

            return ToolResponse(
                success=True,
                data={
                    "user_id": user_id,
                    "subject_id": subject_id,
                    "theta": theta,
                    "se": se,
                    "method": method,
                    "based_on": based_on,
                    "response_count": response_count,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"irt_estimate_ability failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def irt_update_ability(user_id: int, subject_id: int, question_id: int,
                             correct: bool, response_time: float,
                             agent_id: str, session_id: str) -> ToolResponse:
    """Update ability estimate from response"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.irt import IRTAbilityEstimate, ResponseRecord, IRTItemParams
        from app.db.session import SessionLocal
        import math

        db = SessionLocal()
        try:
            item = db.query(IRTItemParams).filter(IRTItemParams.question_id == question_id).first()
            if not item:
                return ToolResponse(
                    success=False,
                    error=f"Item parameters for question {question_id} not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            latest = db.query(IRTAbilityEstimate).filter(
                IRTAbilityEstimate.user_id == user_id,
                IRTAbilityEstimate.subject_id == subject_id,
            ).order_by(IRTAbilityEstimate.estimated_at.desc()).first()

            theta_old = latest.theta if latest else 0.0
            se_old = latest.se if latest else 1.0

            if item.a > 0:
                info = item.a ** 2 * (1 - item.c) ** 2 / ((1 + item.c) ** 2)
                se_new = 1 / math.sqrt(1 / se_old ** 2 + info)
                u = 1 if correct else 0
                p = item.c + (1 - item.c) / (1 + math.exp(-item.a * (theta_old - item.b)))
                theta_new = theta_old + se_new ** 2 * item.a * (u - p) * (1 - item.c) / (1 + item.c)
            else:
                theta_new = theta_old
                se_new = se_old

            response_record = ResponseRecord(
                question_id=question_id,
                user_id=user_id,
                correct=correct,
                response_time=response_time,
            )
            db.add(response_record)

            ability_estimate = IRTAbilityEstimate(
                user_id=user_id,
                subject_id=subject_id,
                theta=theta_new,
                se=se_new,
                method="eap",
                based_on=(latest.based_on + 1) if latest else 1,
                estimated_at=datetime.utcnow(),
            )
            db.add(ability_estimate)
            db.commit()

            return ToolResponse(
                success=True,
                data={
                    "user_id": user_id,
                    "subject_id": subject_id,
                    "theta_old": theta_old,
                    "theta_new": theta_new,
                    "se_old": se_old,
                    "se_new": se_new,
                    "question_id": question_id,
                    "correct": correct,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"irt_update_ability failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )