from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.tutor import TutorSession, TutorMessage
from app.services.tutor_state_machine import TutorStateMachine, TutorState


router = APIRouter(tags=["tutor"])


class StartSessionRequest(BaseModel):
    user_id: int
    concept_id: str


class StartSessionResponse(BaseModel):
    session_id: int
    state: str
    message: str
    kg_citations: List[dict]


class SendMessageRequest(BaseModel):
    content: str
    role: str = "student"


class SendMessageResponse(BaseModel):
    session_id: int
    state: str
    message: str
    hint_level: Optional[int]
    kg_citations: List[dict]
    suggestions: List[str]
    is_final: bool


@router.post("/sessions", response_model=StartSessionResponse)
async def start_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = TutorSession(
        user_id=request.user_id,
        concept_id=request.concept_id,
        current_state="diagnose",
        target_concept_id=request.concept_id
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return StartSessionResponse(
        session_id=session.id,
        state="diagnose",
        message=f"Let's explore {request.concept_id}. What does it mean to you?",
        kg_citations=[]
    )


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: int,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(TutorSession).filter(TutorSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    msg = TutorMessage(
        session_id=session_id,
        role=request.role,
        content=request.content,
        state_at_time=session.current_state
    )
    db.add(msg)

    sm = TutorStateMachine(
        user_id=session.user_id,
        concept_id=session.concept_id,
        session_id=session_id
    )
    sm.state = TutorState(session.current_state)
    sm.turns_in_state = session.turns_in_state
    sm.hint_level = session.hint_level
    sm.misconception = session.misconception

    response = sm.transition(request.content, request.role)

    session.current_state = response.state.value
    session.turns_in_state = sm.turns_in_state
    session.hint_level = sm.hint_level
    session.misconception = sm.misconception

    await db.commit()

    tutor_msg = TutorMessage(
        session_id=session_id,
        role="tutor",
        content=response.message,
        hint_level=response.hint_level,
        state_at_time=response.state.value
    )
    db.add(tutor_msg)
    await db.commit()

    return SendMessageResponse(
        session_id=session_id,
        state=response.state.value,
        message=response.message,
        hint_level=response.hint_level,
        kg_citations=response.kg_citations or [],
        suggestions=response.suggestions or [],
        is_final=response.is_final
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(TutorSession).filter(TutorSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "concept_id": session.concept_id,
        "current_state": session.current_state,
        "turns_in_state": session.turns_in_state,
        "hint_level": session.hint_level,
        "misconception": session.misconception
    }