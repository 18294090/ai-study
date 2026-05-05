from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

from app.mcp.kg_tools import ToolResponse


async def tutor_start_session(user_id: int, concept_id: str, agent_id: str, session_id: str) -> ToolResponse:
    """Start a Socratic tutor session"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.tutor import TutorSession
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            session = TutorSession(
                user_id=user_id,
                concept_id=concept_id,
                target_concept_id=concept_id,
                current_state="diagnose",
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            return ToolResponse(
                success=True,
                data={
                    "session_id": session.id,
                    "user_id": user_id,
                    "concept_id": concept_id,
                    "state": session.current_state,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"tutor_start_session failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def tutor_message(session_id: int, content: str, role: str, agent_id: str, parent_session_id: str) -> ToolResponse:
    """Send message to tutor session"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.tutor import TutorSession, TutorMessage
        from app.services.tutor_state_machine import TutorStateMachine
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
            if not session:
                return ToolResponse(
                    success=False,
                    error=f"Session {session_id} not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            state_machine = TutorStateMachine(
                user_id=session.user_id,
                concept_id=session.target_concept_id,
                session_id=session.id,
            )
            state_machine.state = state_machine.state or state_machine.state
            state_machine.turns_in_state = session.turns_in_state
            state_machine.hint_level = session.hint_level
            state_machine.misconception = session.misconception

            tutor_response = state_machine.transition(content, role)

            message = TutorMessage(
                session_id=session_id,
                role=role,
                content=content,
                hint_level=tutor_response.hint_level,
                state_at_time=tutor_response.state.value,
            )
            db.add(message)

            session.current_state = tutor_response.state.value
            session.turns_in_state = state_machine.turns_in_state
            session.hint_level = state_machine.hint_level
            session.misconception = state_machine.misconception
            db.commit()

            return ToolResponse(
                success=True,
                data={
                    "message": tutor_response.message,
                    "state": tutor_response.state.value,
                    "hint_level": tutor_response.hint_level,
                    "is_final": tutor_response.is_final,
                    "kg_citations": tutor_response.kg_citations,
                    "suggestions": tutor_response.suggestions,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"tutor_message failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def tutor_get_session(session_id: int, agent_id: str, parent_session_id: str) -> ToolResponse:
    """Get current tutor session state"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.tutor import TutorSession, TutorMessage
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            session = db.query(TutorSession).filter(TutorSession.id == session_id).first()
            if not session:
                return ToolResponse(
                    success=False,
                    error=f"Session {session_id} not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            messages = db.query(TutorMessage).filter(
                TutorMessage.session_id == session_id
            ).order_by(TutorMessage.created_at).all()

            return ToolResponse(
                success=True,
                data={
                    "session_id": session.id,
                    "user_id": session.user_id,
                    "concept_id": session.target_concept_id,
                    "current_state": session.current_state,
                    "turns_in_state": session.turns_in_state,
                    "hint_level": session.hint_level,
                    "misconception": session.misconception,
                    "messages": [
                        {
                            "id": m.id,
                            "role": m.role,
                            "content": m.content,
                            "hint_level": m.hint_level,
                            "state_at_time": m.state_at_time,
                            "created_at": m.created_at.isoformat() if m.created_at else None,
                        }
                        for m in messages
                    ],
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"tutor_get_session failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )