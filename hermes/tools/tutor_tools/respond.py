"""tutor_respond tool for Hermes."""

from typing import Dict, Any, List
import os
import json
import logging

logger = logging.getLogger(__name__)

SESSION_DIR = os.path.expanduser("~/.hermes/sessions")

def _get_session_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, f"tutor_{session_id}.json")

def _load_session(session_id: str) -> Dict[str, Any]:
    path = _get_session_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    path = _get_session_path(session_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def _detect_injection(message: str) -> bool:
    blocked = ["ignore previous", "system prompt", "you are now", "/sandbox", "ignore all"]
    msg_lower = message.lower()
    return any(b in msg_lower for b in blocked)

def _sanitize_input(message: str) -> str:
    import re
    message = re.sub(r'```[\s\S]*?```', '[code removed]', message)
    message = re.sub(r'`[^`]+`', '[code removed]', message)
    return message.strip()

def tutor_respond(session_id: str, student_message: str, role: str = "student") -> Dict[str, Any]:
    """Process student message and generate tutor response.

    Args:
        session_id: Session ID
        student_message: Student's message
        role: Message role (student/tutor)

    Returns:
        Dict with message, state, hint_level, kg_citations, suggestions, is_final
    """
    try:
        if _detect_injection(student_message):
            return {
                "success": True,
                "message": "I notice something unusual in your message. Let's stay focused on learning. Can you tell me what you find challenging about this?",
                "state": "diagnose",
                "hint_level": 0,
                "kg_citations": [],
                "suggestions": [],
                "is_final": False
            }

        student_message = _sanitize_input(student_message)

        session = _load_session(session_id)
        if not session:
            return {"success": False, "error": f"Session {session_id} not found", "message": None, "state": None, "hint_level": 0, "kg_citations": [], "suggestions": [], "is_final": False}

        session["messages"].append({
            "role": role,
            "content": student_message
        })

        state = session["current_state"]
        turns = session["turns_in_state"]
        hint_level = session["hint_level"]
        concept_id = session["concept_id"]

        new_state, response_msg, new_hint_level = _state_transition(
            state, turns, hint_level, concept_id, student_message
        )

        session["current_state"] = new_state
        session["turns_in_state"] = turns + 1 if new_state == state else 0
        session["hint_level"] = new_hint_level

        if role == "student":
            session["messages"].append({
                "role": "tutor",
                "content": response_msg,
                "hint_level": new_hint_level
            })

        _save_session(session_id, session)

        is_final = new_state in ["consolidate", "escalate"]

        return {
            "success": True,
            "message": response_msg,
            "state": new_state,
            "hint_level": new_hint_level,
            "kg_citations": [{"concept_id": concept_id, "relation": "relates_to", "target_id": "prerequisite"}],
            "suggestions": _get_suggestions(new_state),
            "is_final": is_final
        }

    except Exception as e:
        logger.error(f"tutor_respond failed: {e}")
        return {"success": False, "error": str(e), "message": None, "state": None, "hint_level": 0, "kg_citations": [], "suggestions": [], "is_final": False}

def _state_transition(state: str, turns: int, hint_level: int, concept_id: str, message: str) -> tuple:
    if state == "diagnose":
        return "hint_ladder", f"That's interesting! You mentioned '{message[:50]}...'. What made you think that?", 0

    elif state == "hint_ladder":
        if "correct" in message.lower() or "right" in message.lower():
            return "counter_example", f"Good progress! Now let me test that understanding...", 0
        if hint_level < 3:
            hints = [
                f"Think about what {concept_id} relates to.",
                f"Remember, {concept_id} requires understanding prerequisites.",
                f"If you have X, then Y follows because..."
            ]
            return "hint_ladder", hints[hint_level], hint_level + 1
        return "guide", f"Let me guide you through {concept_id} step by step.", 0

    elif state == "guide":
        if turns >= 2:
            return "escalate", f"I've noticed we need a different approach. Would you like me to explain directly, or shall I connect you with an expert?", 0
        return "counter_example", f"You're making progress! Let me check your understanding with an example.", 0

    elif state == "counter_example":
        if "understand" in message.lower() or "yes" in message.lower():
            return "consolidate", f"Excellent! Let's summarize what we've learned about {concept_id}.", 0
        return "guide", f"Let's go back and work through the fundamentals again.", 0

    elif state == "consolidate":
        return "consolidate", f"We've covered {concept_id} well. Consider practicing with more problems!", 0

    elif state == "escalate":
        return "escalate", f"I've noted your request. An expert will follow up soon.", 0

    return state, f"Let's continue exploring {concept_id}.", 0

def _get_suggestions(state: str) -> List[str]:
    suggestions = {
        "diagnose": ["Think about examples", "Consider the definition"],
        "hint_ladder": ["Review prerequisites", "Try an example"],
        "guide": ["Follow the steps", "Ask for help if needed"],
        "counter_example": ["Apply the concept", "Check your understanding"],
        "consolidate": ["Practice problems", "Review notes"],
        "escalate": ["Request explanation", "Connect to expert"]
    }
    return suggestions.get(state, [])