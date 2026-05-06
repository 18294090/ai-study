import pytest
from backend.app.hermes.tools.validate_question_tool import validate_question_tool


def test_validate_question_tool_valid_question():
    question = {
        "id": 1,
        "题型": "单选题",
        "内容": "以下哪个是太阳系最大的行星？",
        "选项": ["地球", "火星", "木星", "月球"],
        "置信度": 0.9
    }
    result = validate_question_tool(question)
    assert result["is_valid"] is True
    assert result["issues"] == []


def test_validate_question_tool_invalid_short_content():
    question = {"id": 1, "题型": "单选题", "内容": "短", "置信度": 0.9}
    result = validate_question_tool(question)
    assert result["is_valid"] is False
    assert len(result["issues"]) > 0