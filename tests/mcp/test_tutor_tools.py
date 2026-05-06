import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))

def test_tutor_start_returns_correct_structure():
    from hermes.tools.tutor_tools.start_session import tutor_start

    result = tutor_start(
        user_id=123,
        concept_id="slope",
        p_know=0.3,
        conversation_history=[]
    )

    assert result["success"] is True
    assert "session_id" in result
    assert result["state"] == "diagnose"
    assert "message" in result
    assert isinstance(result["kg_citations"], list)

def test_tutor_start_with_high_p_know():
    from hermes.tools.tutor_tools.start_session import tutor_start

    result = tutor_start(
        user_id=123,
        concept_id="slope",
        p_know=0.7,
        conversation_history=[]
    )

    assert result["success"] is True
    assert result["state"] == "hint_ladder"

def test_tutor_start_error_handling():
    from hermes.tools.tutor_tools.start_session import tutor_start

    result = tutor_start(user_id=None, concept_id="", p_know=0.5)

    assert result["success"] is False
    assert "error" in result