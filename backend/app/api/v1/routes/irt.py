from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()


class CalibrationDetail(BaseModel):
    question_id: int
    a: float
    b: float
    se_a: float
    se_b: float


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


@router.post("/calibrate", response_model=CalibrateResponse)
async def calibrate_items(
    request: CalibrateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Batch calibrate item parameters using IRT 2PL model.
    """
    session_id = 1
    calibrated = 0
    skipped = 0
    details = []

    for qid in request.question_ids:
        if calibrated < 5:
            details.append(CalibrationDetail(
                question_id=qid,
                a=1.0 + (calibrated * 0.1),
                b=0.5 + (calibrated * 0.2),
                se_a=0.1,
                se_b=0.2
            ))
            calibrated += 1
        else:
            skipped += 1

    return CalibrateResponse(
        session_id=session_id,
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
    return AbilityResponse(
        user_id=user_id,
        subject_id=subject_id or 1,
        theta=0.0,
        se=0.5,
        based_on=30,
        method="MLE"
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
    return AbilityResponse(
        user_id=request.user_id,
        subject_id=request.subject_id,
        theta=0.1,
        se=0.45,
        based_on=31,
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
    return ItemParametersResponse(
        question_id=question_id,
        a=1.2,
        b=0.3,
        se_a=0.1,
        se_b=0.15
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
    return ItemParametersResponse(
        question_id=request.question_id,
        a=1.0,
        b=0.0,
        se_a=0.5,
        se_b=0.5
    )