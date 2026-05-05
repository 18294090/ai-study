from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.irt import IRTItemParams, IRTAbilityEstimate, IRTCalibrationSession, ResponseRecord
from app.services.irt_calibration import IRTCalibrationService, Response as IRTResponse
from app.services.irt_ability import IRTAbilityEstimator, AbilityResult

router = APIRouter(prefix="/irt", tags=["irt"])


class CalibrationDetail(BaseModel):
    question_id: int
    a: float
    b: float
    se_a: float
    se_b: float
    converged: bool
    iterations: int


class CalibrateRequest(BaseModel):
    question_ids: List[int]
    method: str = "MLE"
    min_responses: int = 30


class CalibrateResponse(BaseModel):
    session_id: int
    calibrated: int
    skipped: int
    details: List[CalibrationDetail]


class AbilityResponse(BaseModel):
    user_id: int
    subject_id: int
    theta: float
    se: float
    based_on: int
    method: str


class UpdateAbilityRequest(BaseModel):
    user_id: int
    subject_id: int
    question_id: int
    correct: bool
    response_time: float


class LLMEstimationRequest(BaseModel):
    question_id: int
    question_content: str
    options: Optional[dict] = None
    knowledge_points: List[str] = []


class ItemParametersResponse(BaseModel):
    question_id: int
    a: float
    b: float
    se_a: float
    se_b: float


calibration_service = IRTCalibrationService()
ability_estimator = IRTAbilityEstimator()


@router.post("/calibrate", response_model=CalibrateResponse)
async def calibrate_items(
    request: CalibrateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Batch calibrate item parameters using IRT 2PL model.
    """
    session = IRTCalibrationSession(
        subject_id=1,
        method=request.method,
        iterations=0,
        converged=True
    )
    db.add(session)
    await db.flush()

    calibrated = 0
    skipped = 0
    details = []

    for qid in request.question_ids:
        result = await db.execute(
            select(ResponseRecord).filter(ResponseRecord.question_id == qid)
        )
        records = result.scalars().all()

        if len(records) < request.min_responses:
            skipped += 1
            continue

        responses = [
            IRTResponse(ability=0.0, is_correct=r.correct)
            for r in records
        ]

        cal_result = calibration_service.calibrate_item(qid, responses)

        item_params = IRTItemParams(
            question_id=qid,
            model_type="2pl",
            a=cal_result.a,
            b=cal_result.b,
            c=0.0,
            info=0.0,
            sample_size=len(records),
            calibrated_at=datetime.utcnow(),
            status="calibrated" if cal_result.converged else "calibrating",
            metadata_json={"se_a": cal_result.se_a, "se_b": cal_result.se_b}
        )
        db.add(item_params)

        details.append(CalibrationDetail(
            question_id=qid,
            a=cal_result.a,
            b=cal_result.b,
            se_a=cal_result.se_a,
            se_b=cal_result.se_b,
            converged=cal_result.converged,
            iterations=cal_result.iterations
        ))
        calibrated += 1

    await db.commit()

    return CalibrateResponse(
        session_id=session.id,
        calibrated=calibrated,
        skipped=skipped,
        details=details
    )


@router.get("/estimate/{user_id}", response_model=AbilityResponse)
async def get_ability_estimate(
    user_id: int,
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get student ability estimate based on response history.
    """
    if subject_id is None:
        subject_id = 1

    result = await ability_estimator.get_ability(user_id, subject_id, db)
    if result is None:
        return AbilityResponse(
            user_id=user_id,
            subject_id=subject_id,
            theta=0.0,
            se=1.0,
            based_on=0,
            method="EAP"
        )

    return AbilityResponse(
        user_id=user_id,
        subject_id=subject_id,
        theta=round(result.theta, 4),
        se=round(result.se, 4),
        based_on=result.based_on,
        method="EAP"
    )


@router.post("/estimate/ability", response_model=AbilityResponse)
async def update_ability_estimate(
    request: UpdateAbilityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update ability estimate from a single response using online learning.
    """
    result = await ability_estimator.update_from_response(
        user_id=request.user_id,
        subject_id=request.subject_id,
        question_id=request.question_id,
        correct=request.correct,
        response_time=request.response_time,
        db=db
    )

    return AbilityResponse(
        user_id=request.user_id,
        subject_id=request.subject_id,
        theta=round(result.theta, 4),
        se=round(result.se, 4),
        based_on=result.based_on,
        method="EAP"
    )


@router.get("/items/{question_id}", response_model=ItemParametersResponse)
async def get_item_parameters(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get IRT parameters for a specific item (question).
    """
    result = await db.execute(
        select(IRTItemParams).filter(
            IRTItemParams.question_id == question_id,
            IRTItemParams.status == "calibrated"
        ).order_by(IRTItemParams.calibrated_at.desc())
    )
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(status_code=404, detail="Item parameters not found")

    metadata = item.metadata_json or {}
    return ItemParametersResponse(
        question_id=question_id,
        a=item.a,
        b=item.b,
        se_a=metadata.get("se_a", 0.0),
        se_b=metadata.get("se_b", 0.0)
    )


@router.post("/estimate/from-llm", response_model=ItemParametersResponse)
async def estimate_from_llm(
    request: LLMEstimationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cold-start difficulty estimation using LLM analysis.
    """
    from app.services.irt_calibration import Question

    question = Question(
        id=request.question_id,
        content=request.question_content,
        options=[str(o) for o in (request.options or {}).values()] if request.options else []
    )

    from app.core.config import settings
    if hasattr(settings, 'llm_client') and settings.llm_client:
        b_value = await calibration_service.estimate_from_llm(question, settings.llm_client)
    else:
        b_value = 0.0

    item_params = IRTItemParams(
        question_id=request.question_id,
        model_type="2pl",
        a=1.0,
        b=b_value,
        c=0.0,
        info=0.0,
        sample_size=0,
        calibrated_at=datetime.utcnow(),
        status="llm_estimated",
        metadata_json={"source": "llm_cold_start"}
    )
    db.add(item_params)
    await db.commit()

    return ItemParametersResponse(
        question_id=request.question_id,
        a=1.0,
        b=b_value,
        se_a=0.5,
        se_b=0.5
    )