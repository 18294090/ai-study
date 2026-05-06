import pytest
from backend.app.hermes.runtime import HermesRuntime


def test_hermes_runtime_initialization():
    runtime = HermesRuntime()
    assert runtime.tools == {}
    assert runtime._initialized is False


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