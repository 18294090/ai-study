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