"""tutor_get_state tool for Hermes."""

from typing import Dict, Any
import os
import json
import logging

logger = logging.getLogger(__name__)

SESSION_DIR = os.path.expanduser("~/.hermes/sessions")

def _get_session_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, f"tutor_{session_id}.json")

def tutor_get_state(session_id: str) -> Dict[str, Any]:
    """Get current tutor session state.

    Args:
        session_id: Session ID

    Returns:
        Dict with full session state
    """
    try:
        path = _get_session_path(session_id)
        if not os.path.exists(path):
            return {"success": False, "error": f"Session {session_id} not found"}

        with open(path) as f:
            session = json.load(f)

        return {
            "success": True,
            "session_id": session["session_id"],
            "user_id": session["user_id"],
            "concept_id": session["concept_id"],
            "current_state": session["current_state"],
            "turns_in_state": session["turns_in_state"],
            "hint_level": session["hint_level"],
            "misconception": session.get("misconception"),
            "messages": session.get("messages", [])
        }

    except Exception as e:
        logger.error(f"tutor_get_state failed: {e}")
        return {"success": False, "error": str(e)}