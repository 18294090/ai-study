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


def test_validate_question_tool_invalid_type():
    question = {"id": 1, "题型": "非法类型", "内容": "测试内容足够长", "置信度": 0.9}
    result = validate_question_tool(question)
    assert result["is_valid"] is False
    assert any("不在标准类型中" in issue for issue in result["issues"])


def test_validate_question_tool_missing_options():
    question = {"id": 1, "题型": "单选题", "内容": "测试内容足够长"}
    result = validate_question_tool(question)
    assert result["is_valid"] is False
    assert any("缺少选项" in issue for issue in result["issues"])


def test_validate_question_tool_none_options():
    question = {"id": 1, "题型": "单选题", "内容": "测试内容足够长", "选项": None, "置信度": 0.9}
    result = validate_question_tool(question)
    assert result["is_valid"] is False
    assert any("缺少选项" in issue for issue in result["issues"])