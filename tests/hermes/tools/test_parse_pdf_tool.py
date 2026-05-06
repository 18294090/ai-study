import pytest
from backend.app.hermes.tools.parse_pdf_tool import parse_pdf_tool


def test_parse_pdf_tool_returns_expected_keys():
    result = parse_pdf_tool("nonexistent.pdf")
    assert "success" in result
    assert "markdown" in result
    assert "images" in result


def test_parse_pdf_tool_handles_missing_file():
    result = parse_pdf_tool("nonexistent.pdf")
    assert result["success"] is False
    assert "error" in result
