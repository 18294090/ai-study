import pytest
from unittest.mock import patch, MagicMock
from backend.app.hermes.tools.refine_question_tool import refine_question_tool


@patch('app.kg.src.llm_router.LLMRouter')
def test_refine_question_tool_with_mock(mock_router):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '{"题型": "单选题", "内容": "改进后", "置信度": 0.95}'
    mock_client.invoke.return_value = mock_response
    mock_router.return_value.get_client.return_value = mock_client

    question = {"id": 1, "题型": "未知", "内容": "原始", "置信度": 0.3}
    result = refine_question_tool(question)
    assert result["success"] is True
    assert "refined_question" in result


@patch('app.kg.src.llm_router.LLMRouter')
def test_refine_question_tool_json_decode_error(mock_router):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = 'not valid json'
    mock_client.invoke.return_value = mock_response
    mock_router.return_value.get_client.return_value = mock_client

    question = {"id": 1, "题型": "未知", "内容": "原始", "置信度": 0.3}
    result = refine_question_tool(question)
    assert result["success"] is False
    assert "error" in result