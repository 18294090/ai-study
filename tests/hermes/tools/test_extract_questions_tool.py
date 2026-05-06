import pytest
from unittest.mock import patch, MagicMock
from backend.app.hermes.tools.extract_questions_tool import extract_questions_tool


def test_extract_questions_tool_returns_expected_keys():
    result = extract_questions_tool("Sample exam content", "Page 1 of 5")
    assert "success" in result
    assert "questions" in result
    assert isinstance(result["questions"], list)


@patch('app.kg.src.llm_router.LLMRouter')
def test_extract_questions_tool_with_mock(mock_router):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '[{"题型": "单选题", "内容": "测试", "置信度": 0.9}]'
    mock_client.invoke.return_value = mock_response
    mock_router.return_value.get_client.return_value = mock_client

    result = extract_questions_tool("test content")
    assert result["success"] is True
    assert result["count"] == 1
    assert result["truncated"] is False
