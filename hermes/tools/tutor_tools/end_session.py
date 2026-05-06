"""tutor_end tool for Hermes."""

from typing import Dict, Any
import os
import json
import logging

logger = logging.getLogger(__name__)

SESSION_DIR = os.path.expanduser("~/.hermes/sessions")

def _get_session_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, f"tutor_{session_id}.json")

def tutor_end(session_id: str, summary: str = None) -> Dict[str, Any]:
    """End tutor session.

    Args:
        session_id: Session ID
        summary: Optional session summary

    Returns:
        Dict with confirmation
    """
    try:
        path = _get_session_path(session_id)
        if not os.path.exists(path):
            return {"success": False, "error": f"Session {session_id} not found"}

        archive_dir = os.path.join(SESSION_DIR, "archive")
        os.makedirs(archive_dir, exist_ok=True)

        with open(path) as f:
            session = json.load(f)

        if summary:
            session["summary"] = summary

        archive_path = os.path.join(archive_dir, f"tutor_{session_id}.json")
        with open(archive_path, "w") as f:
            json.dump(session, f, indent=2)

        os.remove(path)

        return {
            "success": True,
            "message": "Session ended",
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"tutor_end failed: {e}")
        return {"success": False, "error": str(e)}