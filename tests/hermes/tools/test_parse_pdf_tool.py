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


def test_parse_pdf_tool_error_has_all_keys():
    """Error returns should still have all expected keys."""
    result = parse_pdf_tool("nonexistent.pdf")
    assert result["success"] is False
    assert "char_count" in result
    assert "image_count" in result
    assert result["char_count"] == 0
    assert result["image_count"] == 0
