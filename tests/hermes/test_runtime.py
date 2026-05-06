import pytest
from backend.app.hermes.runtime import HermesRuntime


def test_hermes_runtime_initialization():
    runtime = HermesRuntime()
    assert runtime.tools == {}


def test_register_tool_accepts_callable():
    runtime = HermesRuntime()
    def my_tool(): pass
    runtime.register_tool("my_tool", "desc", {}, my_tool)
    assert "my_tool" in runtime.tools
    assert runtime.tools["my_tool"].handler is my_tool


def test_register_tool_rejects_non_callable():
    runtime = HermesRuntime()
    with pytest.raises(TypeError, match="handler must be callable"):
        runtime.register_tool("bad_tool", "desc", {}, "not_callable")


def test_split_pages_basic():
    runtime = HermesRuntime()
    pages = runtime._split_pages("Page 1 content\n\nPage 2 content")
    assert len(pages) >= 1


def test_split_pages_with_page_breaks():
    runtime = HermesRuntime()
    pages = runtime._split_pages("Content\n---\nMore content")
    assert len(pages) == 2


def test_run_skill_unknown_skill():
    runtime = HermesRuntime()
    result = runtime.run_skill("unknown_skill", {})
    assert result["success"] is False
    assert "Unknown skill" in result["error"]


def test_run_skill_missing_file_path():
    runtime = HermesRuntime()
    result = runtime.run_skill("exam_skill", {})
    assert result["success"] is False
    assert "file_path is required" in result["error"]