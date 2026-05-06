from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.bkt_service import BKTUpdater
from app.models.mastery import MasteryRecord, AnswerLog, DiagnosticResult


router = APIRouter(tags=["mastery"])


class MasteryUpdateRequest(BaseModel):
    user_id: int
    concept_id: str
    question_id: int
    is_correct: bool
    time_elapsed_seconds: Optional[float] = 0


class MasteryUpdateResponse(BaseModel):
    concept_id: str
    p_before: float
    p_after: float
    attempts: int
    correct_count: int


class MasteryQueryResponse(BaseModel):
    user_id: int
    concept_id: str
    p_know: float
    attempts: int
    correct_count: int
    last_updated: Optional[str]


class DiagnoseRequest(BaseModel):
    user_id: int
    concept_ids: List[str]
    questions_per_concept: int = 5


class DiagnoseResponse(BaseModel):
    diagnostics: List[dict]
    questions: List[dict]


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    request: DiagnoseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Initialize mastery via diagnostic test"""
    updater = BKTUpdater()
    
    questions = []
    diagnostics = []
    
    for concept_id in request.concept_ids:
        for i in range(request.questions_per_concept):
            questions.append({
                "concept_id": concept_id,
                "question_id": 1000 + i,
                "question_text": f"Diagnostic Q{i+1} for {concept_id}"
            })
        
        diagnostics.append({
            "concept_id": concept_id,
            "initial_p": 0.3
        })
    
    return DiagnoseResponse(diagnostics=diagnostics, questions=questions)


@router.put("/update", response_model=MasteryUpdateResponse)
async def update_mastery(
    request: MasteryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update mastery after an answer"""
    updater = BKTUpdater()
    
    result = await db.execute(
        select(MasteryRecord).filter(
            MasteryRecord.user_id == request.user_id,
            MasteryRecord.concept_id == request.concept_id
        )
    )
    record = result.scalar_one_or_none()
    
    if record:
        p_before = record.p_know
        p_after = updater.update(p_before, request.is_correct)
        
        if request.time_elapsed_seconds:
            hours = request.time_elapsed_seconds / 3600
            p_after = updater.apply_forget(p_after, hours)
        
        record.p_know = p_after
        record.attempts += 1
        if request.is_correct:
            record.correct_count += 1
    else:
        p_before = 0.3
        p_after = updater.compute_initial_p(
            correct_count=1 if request.is_correct else 0,
            total_attempts=1
        )
        record = MasteryRecord(
            user_id=request.user_id,
            concept_id=request.concept_id,
            p_know=p_after,
            attempts=1,
            correct_count=1 if request.is_correct else 0
        )
        db.add(record)
    
    answer_log = AnswerLog(
        user_id=request.user_id,
        concept_id=request.concept_id,
        question_id=request.question_id,
        is_correct=request.is_correct,
        bkt_p_before=p_before,
        bkt_p_after=p_after
    )
    db.add(answer_log)
    await db.commit()
    
    return MasteryUpdateResponse(
        concept_id=request.concept_id,
        p_before=p_before,
        p_after=p_after,
        attempts=record.attempts,
        correct_count=record.correct_count
    )


@router.get("/{user_id}/{concept_id}", response_model=MasteryQueryResponse)
async def get_mastery(
    user_id: int,
    concept_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get mastery for a specific concept"""
    result = await db.execute(
        select(MasteryRecord).filter(
            MasteryRecord.user_id == user_id,
            MasteryRecord.concept_id == concept_id
        )
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Mastery record not found")
    
    return MasteryQueryResponse(
        user_id=record.user_id,
        concept_id=record.concept_id,
        p_know=record.p_know,
        attempts=record.attempts,
        correct_count=record.correct_count,
        last_updated=str(record.last_updated) if record.last_updated else None
    )


@router.get("/{user_id}")
async def get_all_mastery(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all mastery records for a user"""
    result = await db.execute(
        select(MasteryRecord).filter(MasteryRecord.user_id == user_id)
    )
    records = result.scalars().all()
    
    return {
        "user_id": user_id,
        "masteries": [
            {
                "concept_id": r.concept_id,
                "p_know": r.p_know,
                "attempts": r.attempts,
                "correct_count": r.correct_count
            }
            for r in records
        ]
    }