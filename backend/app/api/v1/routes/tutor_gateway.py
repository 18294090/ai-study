"""Tutor Gateway - FastAPI routes that proxy to Hermes via MCP."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(tags=["tutor"])


class StartSessionRequest(BaseModel):
    user_id: int
    concept_id: str


class SendMessageRequest(BaseModel):
    content: str
    role: str = "student"


@router.post("/sessions")
async def start_session(
    request: StartSessionRequest,
    current_user: User = Depends(get_current_user)
):
    """Start a new tutor session via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        p_know = 0.5
        
        client = await get_hermes_client()
        result = await client.call_tool("tutor_start", {
            "user_id": request.user_id,
            "concept_id": request.concept_id,
            "p_know": p_know,
            "conversation_history": []
        })
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get tutor session state via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("tutor_get_state", {
            "session_id": session_id
        })
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Send message to tutor session via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("tutor_respond", {
            "session_id": session_id,
            "student_message": request.content,
            "role": request.role
        })
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def end_session(
    session_id: str,
    summary: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """End tutor session via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("tutor_end", {
            "session_id": session_id,
            "summary": summary
        })
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))