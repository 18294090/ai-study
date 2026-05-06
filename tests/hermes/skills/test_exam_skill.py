import pytest
from backend.app.hermes.skills.exam_skill import ExamSkill, run_exam_skill


def test_exam_skill_initialization():
    skill = ExamSkill()
    assert skill.config.confidence_threshold == 0.6


def test_exam_skill_has_expected_tools():
    skill = ExamSkill()
    tools = skill.get_tools()
    assert "parse_pdf_tool" in tools
    assert "extract_questions_tool" in tools


@pytest.mark.asyncio
async def test_run_exam_skill_missing_file_path():
    result = await run_exam_skill({})
    assert result["success"] is False


@pytest.mark.asyncio
async def test_run_exam_skill_with_source():
    result = await run_exam_skill({"file_path": "test.pdf", "source": "upload"})
    if result.get("success"):
        assert result["metadata"].get("source") == "upload"