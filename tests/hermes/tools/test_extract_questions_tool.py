import pytest
from backend.app.hermes.tools.extract_questions_tool import extract_questions_tool


def test_extract_questions_tool_returns_expected_keys():
    result = extract_questions_tool("Sample exam content", "Page 1 of 5")
    assert "success" in result
    assert "questions" in result
    assert isinstance(result["questions"], list)
