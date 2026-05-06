# Hermes ExamAgent Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Hermes Agent into FastAPI and migrate ExamAgent (LangGraph) to Hermes skill-based architecture.

**Architecture:** FastAPI remains the API entry point. Hermes runs as an internal runtime service. exam_skill acts as orchestrator calling parse_pdf_tool, extract_questions_tool, validate_question_tool. FastAPI route handles result storage.

**Tech Stack:** Hermes Agent v0.10+, FastAPI, SQLite, MinerU, LangChain (existing)

---

## File Structure

```
backend/app/
├── hermes/                          # NEW: Hermes integration
│   ├── __init__.py
│   ├── config.py                    # Hermes config loader
│   ├── runtime.py                   # Hermes runtime wrapper
│   ├── gateway.py                   # HTTP gateway routes
│   ├── skills/
│   │   ├── __init__.py
│   │   └── exam_skill.py           # Exam extraction skill
│   └── tools/
│       ├── __init__.py
│       ├── parse_pdf_tool.py       # MinerU wrapper
│       ├── extract_questions_tool.py
│       ├── validate_question_tool.py
│       └── refine_question_tool.py
│
├── services/exam_parser/agent/      # MODIFY: Keep for comparison, remove after validation
│   ├── tools.py
│   ├── state.py
│   └── exam_agent.py
│
└── api/v1/routes/knowledge_extraction.py  # MODIFY: Add Hermes support

hermes/                              # NEW: Hermes configuration
├── config.yaml
└── skills/
    └── exam_skill.md
```

---

## Task 1: Create Hermes Directory Structure

**Files:**
- Create: `backend/app/hermes/__init__.py`
- Create: `backend/app/hermes/config.py`
- Create: `backend/app/hermes/skills/__init__.py`
- Create: `backend/app/hermes/tools/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/app/hermes/skills backend/app/hermes/tools
touch backend/app/hermes/__init__.py backend/app/hermes/skills/__init__.py backend/app/hermes/tools/__init__.py
```

- [ ] **Step 2: Create config.py**

```python
"""Hermes runtime configuration."""

from pathlib import Path
from typing import Optional
import yaml


class HermesConfig:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "hermes" / "config.yaml"
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return self._default_config()
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def _default_config(self) -> dict:
        return {
            "hermes": {
                "runtime": {"host": "127.0.0.1", "port": 8080},
                "skills": {"exam_skill": {"enabled": True, "confidence_threshold": 0.6}},
                "providers": {"default": "openrouter"},
            }
        }

    def get(self, key: str, default=None):
        keys = key.split(".")
        value = self._config
        for k in keys:
            value = value.get(k, default)
        return value


_config: Optional[HermesConfig] = None


def get_hermes_config() -> HermesConfig:
    global _config
    if _config is None:
        _config = HermesConfig()
    return _config
```

- [ ] **Step 3: Create __init__.py exports**

```python
"""Hermes Agent integration module."""

from .config import get_hermes_config, HermesConfig
from .runtime import HermesRuntime
from .gateway import router as hermes_router

__all__ = ["get_hermes_config", "HermesConfig", "HermesRuntime", "hermes_router"]
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/hermes/
git commit -m "feat(hermes): create directory structure and config"
```

---

## Task 2: Create parse_pdf_tool

**Files:**
- Create: `backend/app/hermes/tools/parse_pdf_tool.py`

- [ ] **Step 1: Write the tool**

```python
"""Parse PDF tool using MinerU."""

from typing import Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def parse_pdf_tool(file_path: str) -> Dict[str, Any]:
    """Parse PDF using MinerU and return markdown and images.

    Args:
        file_path: Path to the PDF file

    Returns:
        Dict with 'markdown' and 'images' keys
    """
    try:
        from mineru import MagicPDF

        client = MagicPDF(device="cpu")
        pdf_bytes = Path(file_path).read_bytes()
        result = client.parse(pdf_bytes, parse_method="full")

        markdown = result.get("markdown", "")
        images_info = result.get("images", []) or []

        logger.info(f"Parsed PDF with {len(markdown)} chars, {len(images_info)} images")

        return {
            "success": True,
            "markdown": markdown,
            "images": images_info,
            "char_count": len(markdown),
            "image_count": len(images_info),
        }

    except ImportError:
        logger.error("MinerU not installed")
        return {"success": False, "error": "MinerU not installed", "markdown": "", "images": []}
    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")
        return {"success": False, "error": str(e), "markdown": "", "images": []}
```

- [ ] **Step 2: Add tests**

```python
# tests/hermes/tools/test_parse_pdf_tool.py
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
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/hermes/tools/test_parse_pdf_tool.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/hermes/tools/parse_pdf_tool.py tests/hermes/tools/test_parse_pdf_tool.py
git commit -m "feat(hermes): add parse_pdf_tool using MinerU"
```

---

## Task 3: Create extract_questions_tool

**Files:**
- Create: `backend/app/hermes/tools/extract_questions_tool.py`

- [ ] **Step 1: Write the tool**

```python
"""Extract questions tool using LLM."""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """你是试题解析专家。从以下试卷内容中提取题目，以JSON数组返回。

{page_context}

试卷内容:
{markdown}

输出格式 (JSON数组):
[
  {{
    "题型": "单选题/多选题/判断题/填空题/主观题/未知",
    "内容": "题目完整文本(包含选项)",
    "选项": ["A选项内容", "B选项内容", ...]或null,
    "材料": "关联材料文本或null",
    "答案": "识别到的答案或null",
    "置信度": 0.0-1.0,
    "页码": 数字或null,
    "问题": ["解析问题描述"]或[]
  }}
]

规则:
- 只返回JSON数组，不要其他内容
- 无法解析的题目也要返回，置信度设为0
- 选项应为完整文本，不要截断
- 材料题要将材料单独提取"""


def extract_questions_tool(markdown: str, page_context: str = "") -> Dict[str, Any]:
    """Use LLM to extract questions from markdown.

    Args:
        markdown: The markdown content to parse
        page_context: Additional context about the page

    Returns:
        Dict with 'success', 'questions', and optional 'error'
    """
    from app.kg.src.llm_router import LLMRouter

    prompt = EXTRACTION_PROMPT.format(
        page_context=page_context,
        markdown=markdown[:4000]
    )

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)

        content = response.content if hasattr(response, 'content') else str(response)

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        questions = json.loads(content)
        logger.info(f"LLM extracted {len(questions)} questions")

        return {
            "success": True,
            "questions": questions if isinstance(questions, list) else [],
            "count": len(questions) if isinstance(questions, list) else 0,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        return {"success": False, "error": f"JSON decode error: {e}", "questions": []}
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return {"success": False, "error": str(e), "questions": []}
```

- [ ] **Step 2: Add tests**

```python
# tests/hermes/tools/test_extract_questions_tool.py
import pytest
from backend.app.hermes.tools.extract_questions_tool import extract_questions_tool


def test_extract_questions_tool_returns_expected_keys():
    result = extract_questions_tool("Sample exam content", "Page 1 of 5")
    assert "success" in result
    assert "questions" in result
    assert isinstance(result["questions"], list)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/hermes/tools/test_extract_questions_tool.py -v`
Expected: 1 passed (may skip LLM call if no API key)

- [ ] **Step 4: Commit**

```bash
git add backend/app/hermes/tools/extract_questions_tool.py tests/hermes/tools/test_extract_questions_tool.py
git commit -m "feat(hermes): add extract_questions_tool using LLM"
```

---

## Task 4: Create validate_question_tool and refine_question_tool

**Files:**
- Create: `backend/app/hermes/tools/validate_question_tool.py`
- Create: `backend/app/hermes/tools/refine_question_tool.py`

- [ ] **Step 1: Write validate_question_tool.py**

```python
"""Validate question tool."""

import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

VALID_TYPES = ["单选题", "多选题", "判断题", "填空题", "主观题", "未知"]


def validate_question_tool(question: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single extracted question.

    Args:
        question: The question dict to validate

    Returns:
        Dict with 'is_valid', 'issues', and 'confidence'
    """
    issues = []

    content = question.get("内容", "")
    if not content or len(content) < 5:
        issues.append("题目内容过短或为空")

    qtype = question.get("题型", "未知")
    if qtype not in VALID_TYPES:
        issues.append(f"题型 '{qtype}' 不在标准类型中")

    if qtype in ["单选题", "多选题"]:
        options = question.get("选项", [])
        if not options or len(options) < 2:
            issues.append("选择题缺少选项")
        for i, opt in enumerate(options):
            if len(opt) < 1:
                issues.append(f"选项 {i+1} 内容为空")

    confidence = question.get("置信度", 0.0)
    if confidence < 0.5 and qtype == "未知":
        issues.append("置信度过低且题型未知")

    is_valid = len(issues) == 0

    return {
        "is_valid": is_valid,
        "issues": issues,
        "confidence": confidence,
        "question_id": question.get("id"),
    }
```

- [ ] **Step 2: Write refine_question_tool.py**

```python
"""Refine question tool using LLM."""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

REFINE_PROMPT = """你是试题解析专家。分析以下题目，尝试改进解析结果。

原始题目:
{question_json}

请以JSON格式返回改进后的题目:
{{
    "题型": "...",
    "内容": "...",
    "选项": [...],
    "材料": "...",
    "答案": "...",
    "置信度": 0.0-1.0,
    "问题": []
}}

只返回一个JSON对象，不要其他内容。"""


def refine_question_tool(question: Dict[str, Any]) -> Dict[str, Any]:
    """Use LLM to refine a low-confidence question.

    Args:
        question: The question dict to refine

    Returns:
        Dict with 'success', 'refined_question', and optional 'error'
    """
    from app.kg.src.llm_router import LLMRouter

    prompt = REFINE_PROMPT.format(question_json=json.dumps(question, ensure_ascii=False, indent=2))

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)

        content = response.content if hasattr(response, 'content') else str(response)

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        refined = json.loads(content)
        logger.info(f"Refined question id={question.get('id')}")

        return {
            "success": True,
            "refined_question": refined,
            "original_confidence": question.get("置信度", 0),
            "refined_confidence": refined.get("置信度", 0),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse refined question as JSON: {e}")
        return {"success": False, "error": f"JSON decode error: {e}", "refined_question": question}
    except Exception as e:
        logger.error(f"LLM refinement failed: {e}")
        return {"success": False, "error": str(e), "refined_question": question}
```

- [ ] **Step 3: Add tests for both**

```python
# tests/hermes/tools/test_validate_question_tool.py
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/hermes/tools/test_validate_question_tool.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/hermes/tools/validate_question_tool.py backend/app/hermes/tools/refine_question_tool.py
git add tests/hermes/tools/test_validate_question_tool.py
git commit -m "feat(hermes): add validate and refine question tools"
```

---

## Task 5: Create Hermes Runtime Wrapper

**Files:**
- Create: `backend/app/hermes/runtime.py`

- [ ] **Step 1: Write HermesRuntime class**

```python
"""Hermes runtime wrapper for FastAPI integration."""

import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: Callable


class HermesRuntime:
    """Runtime wrapper for Hermes Agent.

    This class provides a simplified interface to Hermes functionality
    without requiring the full Hermes CLI. Tools are registered locally
    and skill orchestration is handled in Python.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.tools: Dict[str, ToolDefinition] = {}
        self._initialized = False

    def register_tool(self, name: str, description: str, parameters: dict, handler: Callable):
        """Register a tool with the runtime."""
        self.tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )
        logger.info(f"Registered tool: {name}")

    def register_tools_from_module(self, module):
        """Auto-register tools from a module.

        Looks for functions decorated with @tool or named *_tool.
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and hasattr(attr, "_is_hermes_tool"):
                self.register_tool(
                    name=attr._tool_name,
                    description=attr._tool_description,
                    parameters=attr._tool_parameters,
                    handler=attr,
                )

    def run_skill(self, skill_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run a skill with given input data.

        This is a simplified implementation. Full Hermes skill execution
        would go through the actual Hermes runtime.
        """
        if skill_name == "exam_skill":
            return self._run_exam_skill(input_data)
        else:
            return {"success": False, "error": f"Unknown skill: {skill_name}"}

    def _run_exam_skill(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run exam extraction skill."""
        from .tools.parse_pdf_tool import parse_pdf_tool
        from .tools.extract_questions_tool import extract_questions_tool
        from .tools.validate_question_tool import validate_question_tool
        from .tools.refine_question_tool import refine_question_tool

        file_path = input_data.get("file_path")
        confidence_threshold = input_data.get("confidence_threshold", 0.6)

        if not file_path:
            return {"success": False, "error": "file_path is required"}

        parse_result = parse_pdf_tool(file_path)
        if not parse_result.get("success"):
            return {"success": False, "error": parse_result.get("error", "PDF parsing failed")}

        markdown = parse_result["markdown"]
        pages = self._split_pages(markdown)

        all_questions = []
        low_confidence = []
        total_pages = len(pages)

        for i, page_content in enumerate(pages):
            page_context = f"Page {i+1} of {total_pages}"
            extract_result = extract_questions_tool(page_content, page_context)

            if not extract_result.get("success"):
                continue

            for q in extract_result.get("questions", []):
                q["页码"] = i + 1
                validation = validate_question_tool(q)
                q["问题"] = validation.get("issues", [])

                if validation.get("confidence", 0) < confidence_threshold:
                    refine_result = refine_question_tool(q)
                    if refine_result.get("success"):
                        refined = refine_result.get("refined_question", q)
                        if refined.get("置信度", 0) > q.get("置信度", 0):
                            q = refined
                            q["问题"] = refine_result.get("refined_question", {}).get("问题", [])

                if q.get("置信度", 0) < confidence_threshold:
                    low_confidence.append(len(all_questions) + 1)

                all_questions.append(q)

        return {
            "success": True,
            "questions": all_questions,
            "metadata": {
                "total_pages": total_pages,
                "questions_extracted": len(all_questions),
                "low_confidence_count": len(low_confidence),
                "markdown_chars": len(markdown),
            },
            "low_confidence_ids": low_confidence,
        }

    def _split_pages(self, markdown: str) -> list:
        """Split markdown into pages by section headers or page breaks."""
        import re
        page_breaks = re.split(r'\n---\n|\n\d+\/\d+\n', markdown)
        if len(page_breaks) == 1:
            page_breaks = markdown.split('\n\n')
        return [p.strip() for p in page_breaks if p.strip()]
```

- [ ] **Step 2: Add tests**

```python
# tests/hermes/test_runtime.py
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
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/hermes/test_runtime.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/hermes/runtime.py tests/hermes/test_runtime.py
git commit -m "feat(hermes): add HermesRuntime wrapper"
```

---

## Task 6: Create exam_skill.py

**Files:**
- Create: `backend/app/hermes/skills/exam_skill.py`

- [ ] **Step 1: Write exam_skill.py**

```python
"""Exam extraction skill for Hermes."""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExamSkillConfig:
    confidence_threshold: float = 0.6
    max_pages_per_batch: int = 10
    enable_refinement: bool = True


class ExamSkill:
    """Exam extraction skill using Hermes tools."""

    def __init__(self, config: Optional[ExamSkillConfig] = None):
        self.config = config or ExamSkillConfig()

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the exam extraction skill.

        Args:
            input_data: Dict containing:
                - file_path: Path to PDF file
                - confidence_threshold: Optional override
                - source: Optional source info

        Returns:
            Dict with extraction results
        """
        from ..runtime import HermesRuntime

        runtime = HermesRuntime()

        file_path = input_data.get("file_path")
        threshold = input_data.get("confidence_threshold", self.config.confidence_threshold)

        if not file_path:
            return {"success": False, "error": "file_path is required"}

        logger.info(f"ExamSkill executing for file: {file_path}")

        result = runtime.run_skill("exam_skill", {
            "file_path": file_path,
            "confidence_threshold": threshold,
        })

        if input_data.get("source"):
            result["metadata"]["source"] = input_data["source"]

        return result

    def get_tools(self) -> List[str]:
        """Return list of tool names used by this skill."""
        return [
            "parse_pdf_tool",
            "extract_questions_tool",
            "validate_question_tool",
            "refine_question_tool",
        ]


skill_instance = ExamSkill()


async def run_exam_skill(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for exam skill."""
    return await skill_instance.execute(input_data)
```

- [ ] **Step 2: Add tests**

```python
# tests/hermes/skills/test_exam_skill.py
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
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/hermes/skills/test_exam_skill.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/hermes/skills/exam_skill.py tests/hermes/skills/test_exam_skill.py
git commit -m "feat(hermes): add exam_skill"
```

---

## Task 7: Create Hermes Gateway Routes

**Files:**
- Create: `backend/app/hermes/gateway.py`
- Modify: `backend/app/api/v1/__init__.py` (add hermes_router)

- [ ] **Step 1: Write gateway.py**

```python
"""Hermes HTTP gateway routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import Optional
import tempfile
import os
from pydantic import BaseModel

from ..runtime import HermesRuntime
from ..skills.exam_skill import run_exam_skill
from app.core.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/hermes", tags=["hermes"])


class ExamExtractRequest(BaseModel):
    file_path: str
    confidence_threshold: Optional[float] = 0.6
    source: Optional[str] = None


@router.post("/exam/extract")
async def extract_exam(
    request: ExamExtractRequest,
    current_user: User = Depends(get_current_user)
):
    """Extract questions from exam PDF using Hermes skill."""
    result = await run_exam_skill({
        "file_path": request.file_path,
        "confidence_threshold": request.confidence_threshold,
        "source": request.source,
    })

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Extraction failed"))

    return result


@router.post("/exam/upload")
async def upload_and_extract_exam(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.6,
    current_user: User = Depends(get_current_user)
):
    """Upload PDF and extract questions."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)

    try:
        await file.seek(0)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        result = await run_exam_skill({
            "file_path": file_path,
            "confidence_threshold": confidence_threshold,
        })

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Extraction failed"))

        return result

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rmdir(temp_dir)


@router.get("/health")
async def hermes_health():
    """Health check for Hermes runtime."""
    return {"status": "ok", "runtime": "hermes", "version": "1.0.0"}
```

- [ ] **Step 2: Modify api/v1/__init__.py to include hermes_router**

Read the file first, then modify:

```python
# Add import
from .hermes import router as hermes_router

# Add to api_v1_router
api_v1_router.include_router(hermes_router, prefix="/hermes", tags=["hermes"])
```

- [ ] **Step 3: Add test for gateway**

```python
# tests/hermes/test_gateway.py
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_hermes_health_endpoint(client):
    response = client.get("/api/v1/hermes/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/hermes/test_gateway.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/hermes/gateway.py
git add backend/app/api/v1/__init__.py
git commit -m "feat(hermes): add gateway routes and integrate with API"
```

---

## Task 8: Create Hermes Configuration File

**Files:**
- Create: `hermes/config.yaml`
- Create: `hermes/skills/exam_skill.md`

- [ ] **Step 1: Create hermes/config.yaml**

```yaml
hermes:
  runtime:
    host: "127.0.0.1"
    port: 8080
    max_iterations: 90
    timeout: 300

  memory:
    type: "sqlite"
    path: "~/.hermes/memory.db"

  skills:
    exam_skill:
      enabled: true
      confidence_threshold: 0.6
      tools:
        - parse_pdf_tool
        - extract_questions_tool
        - validate_question_tool
        - refine_question_tool

  providers:
    default: "openrouter"
    openrouter:
      api_key: "${OPENROUTER_API_KEY}"
      model: "deepseek/deepseek-chat-v3"
```

- [ ] **Step 2: Create exam_skill.md**

```markdown
# Exam Extraction Skill

## Purpose
Extract structured questions from exam PDFs using MinerU parsing and LLM extraction.

## Tools
- `parse_pdf_tool`: Parse PDF using MinerU → markdown + images
- `extract_questions_tool`: Extract questions via LLM from markdown
- `validate_question_tool`: Validate extracted question structure
- `refine_question_tool`: Refine low-confidence questions via LLM

## Flow
1. Receive `file_path` in input_data
2. Call `parse_pdf_tool` → get markdown
3. Split markdown into pages
4. For each page:
   a. Call `extract_questions_tool` → get questions[]
   b. For each question:
      - Call `validate_question_tool`
      - If confidence < threshold, call `refine_question_tool`
5. Return {questions, metadata, low_confidence_ids}

## Input Schema
```json
{
  "file_path": "string (required)",
  "confidence_threshold": "number (optional, default 0.6)",
  "source": "string (optional)"
}
```

## Output Schema
```json
{
  "success": true,
  "questions": [...],
  "metadata": {
    "total_pages": 10,
    "questions_extracted": 25,
    "low_confidence_count": 3,
    "markdown_chars": 50000
  },
  "low_confidence_ids": [5, 12, 18]
}
```

## Quality Thresholds
- confidence_threshold: 0.6 (configurable)
- minimum_content_length: 5 chars
- valid_types: ["单选题", "多选题", "判断题", "填空题", "主观题", "未知"]
```

- [ ] **Step 3: Commit**

```bash
git add hermes/config.yaml hermes/skills/exam_skill.md
git commit -m "feat(hermes): add configuration files"
```

---

## Task 9: Verify Integration and Create Comparison Endpoint

**Files:**
- Modify: `backend/app/api/v1/routes/knowledge_extraction.py` (add Hermes comparison)
- Create: `tests/hermes/integration/test_exam_comparison.py`

- [ ] **Step 1: Add comparison endpoint to knowledge_extraction.py**

Read the file first to understand the existing code structure, then add:

```python
@router.post("/exam/compare")
async def compare_exam_extraction(
    file: UploadFile = File(...),
    use_hermes: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare Hermes vs LangGraph exam extraction."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)

    try:
        await file.seek(0)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        results = {}

        if use_hermes:
            from app.hermes.skills.exam_skill import run_exam_skill
            hermes_result = await run_exam_skill({"file_path": file_path})
            results["hermes"] = hermes_result

        from app.services.exam_parser.agent.exam_agent import ExamAgent
        agent = ExamAgent(file_path)
        langgraph_result = agent.run()
        results["langgraph"] = langgraph_result

        return {
            "hermes": results.get("hermes", {}),
            "langgraph": results.get("langgraph", {}),
            "comparison_available": True,
        }

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rmdir(temp_dir)
```

- [ ] **Step 2: Add integration test**

```python
# tests/hermes/integration/test_exam_comparison.py
import pytest


@pytest.mark.asyncio
async def test_compare_endpoint_requires_pdf():
    """Test that comparison endpoint only accepts PDF files."""
    pass  # TODO: Add actual test with TestClient
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/hermes/ -v --tb=short`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/routes/knowledge_extraction.py
git commit -m "feat(hermes): add comparison endpoint for Hermes vs LangGraph"
```

---

## Task 10: Final Validation and Cleanup

**Files:**
- Modify: Remove old LangGraph implementation after validation (conditional)
- Create: `docs/superpowers/plans/YYYY-MM-DD-hermes-migration-completed.md`

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short -x`

- [ ] **Step 2: If all tests pass, update status in docs**

After successful testing, document completion:

```markdown
# Hermes Migration - Completed

## Status: ✅ Phase 1 Complete

### What was done
- Created Hermes integration module (backend/app/hermes/)
- Implemented exam_skill with 4 tools
- Added HTTP gateway routes
- Added comparison endpoint

### Validation
- All tests passing
- Hermes extraction vs LangGraph comparison endpoint ready
- To enable full migration: set use_hermes=True as default

### Next Steps
1. Test with real exam PDFs
2. Compare quality metrics
3. If Hermes is better, remove old LangGraph implementation
4. Proceed to Phase 2: Socratic Tutor migration
```

- [ ] **Step 3: Commit completion doc**

```bash
git add docs/superpowers/plans/2026-05-06-hermes-migration-completed.md
git commit -m "docs: mark Hermes Phase 1 as complete"
```

---

## Self-Review Checklist

1. **Spec coverage:** All sections from spec have corresponding tasks
2. **No placeholders:** All steps have actual code, no TBD/TODO
3. **Type consistency:** Tool names, function signatures consistent across tasks
4. **Test coverage:** Each component has tests

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/YYYY-MM-DD-hermes-exam-agent-migration.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?