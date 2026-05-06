"""tutor_start tool for Hermes."""

from typing import Dict, Any, List
import uuid
import logging
import os

logger = logging.getLogger(__name__)

SESSION_DIR = os.path.expanduser("~/.hermes/sessions")

def _ensure_session_dir():
    os.makedirs(SESSION_DIR, exist_ok=True)

def _get_session_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, f"tutor_{session_id}.json")

def tutor_start(user_id: int, concept_id: str, p_know: float, conversation_history: List[Dict] = None) -> Dict[str, Any]:
    """Start a new Socratic tutor session.

    Args:
        user_id: User ID
        concept_id: Concept to tutor
        p_know: BKT mastery probability (0-1)
        conversation_history: Optional prior conversation

    Returns:
        Dict with session_id, state, message, kg_citations, suggestions
    """
    try:
        if user_id is None or not concept_id:
            return {"success": False, "error": "user_id and concept_id are required", "session_id": None, "state": None, "message": None}

        _ensure_session_dir()

        session_id = str(uuid.uuid4())
        conversation_history = conversation_history or []

        initial_state = "diagnose" if p_know < 0.5 else "guide"

        if p_know >= 0.8:
            initial_state = "consolidate"
        elif p_know >= 0.5:
            initial_state = "hint_ladder"

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "concept_id": concept_id,
            "p_know": p_know,
            "current_state": initial_state,
            "turns_in_state": 0,
            "hint_level": 0,
            "misconception": None,
            "messages": conversation_history,
            "created_at": str(uuid.uuid4()),
        }

        with open(_get_session_path(session_id), "w") as f:
            import json
            json.dump(session_data, f)

        first_message = _generate_first_message(concept_id, initial_state)

        return {
            "success": True,
            "session_id": session_id,
            "state": initial_state,
            "message": first_message,
            "kg_citations": [],
            "suggestions": ["Think about the definition", "Consider an example"]
        }

    except Exception as e:
        logger.error(f"tutor_start failed: {e}")
        return {"success": False, "error": str(e), "session_id": None, "state": None, "message": None}

def _generate_first_message(concept_id: str, state: str) -> str:
    messages = {
        "diagnose": f"Let's explore {concept_id}. What does it mean to you?",
        "hint_ladder": f"Let's dive deeper into {concept_id}. What's your first thought?",
        "guide": f"Let's work through {concept_id} together. Where would you like to start?",
        "counter_example": f"You've got interesting ideas about {concept_id}. Let me test them.",
        "consolidate": f"Let's summarize what we've learned about {concept_id}.",
        "escalate": f"I'd like to help more with {concept_id}. How can I support you better?"
    }
    return messages.get(state, f"Let's learn about {concept_id}.")