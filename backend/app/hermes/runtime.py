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
        self.tools: Dict[str, ToolDefinition] = {}

    def register_tool(self, name: str, description: str, parameters: dict, handler: Callable):
        """Register a tool with the runtime."""
        if not callable(handler):
            raise TypeError("handler must be callable")
        self.tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )
        logger.info(f"Registered tool: {name}")

    def register_tools_from_module(self, module):
        """Auto-register tools from a module.

        Looks for functions named *_tool.
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and attr_name.endswith("_tool"):
                self.register_tool(
                    name=attr_name,
                    description="",
                    parameters={},
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