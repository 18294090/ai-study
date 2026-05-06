"""Exam extraction agent state definitions."""

from typing import TypedDict, List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REFINEMENT = "needs_refinement"


class QuestionType(str, Enum):
    SINGLE_CHOICE = "单选题"
    MULTIPLE_CHOICE = "多选题"
    TRUE_FALSE = "判断题"
    FILL_BLANK = "填空题"
    SUBJECTIVE = "主观题"
    UNKNOWN = "未知"


@dataclass
class ExtractedQuestion:
    """A single extracted question."""
    id: int
    raw_text: str
    question_type: str = QuestionType.UNKNOWN.value
    content: str = ""
    options: List[str] = field(default_factory=list)
    answer: Optional[str] = None
    material: Optional[str] = None
    images: List[str] = field(default_factory=list)
    confidence: float = 0.0
    page_num: Optional[int] = None
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "题型": self.question_type,
            "内容": self.content,
            "选项": self.options,
            "答案": self.answer,
            "材料": self.material,
            "配图": self.images,
            "置信度": self.confidence,
            "页码": self.page_num,
            "问题": self.issues,
        }


@dataclass
class PageContext:
    """Context for a single page."""
    page_num: int
    markdown: str
    questions_found: List[int] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)


class ExamAgentState(TypedDict):
    """State for the exam extraction agent."""

    # Input
    file_path: str
    source: str

    # Parsed content
    raw_markdown: str
    pages: List[PageContext]

    # Extraction progress
    status: str
    questions: List[Dict[str, Any]]
    current_page: int
    total_pages: int

    # Memory for cross-page dependencies
    pending_materials: List[str]
    pending_answers: List[str]
    last_question_id: int

    # Quality control
    confidence_threshold: float
    low_confidence_questions: List[int]
    refinement_needed: bool

    # Output
    extraction_report: Dict[str, Any]
    errors: List[str]


def initial_state(file_path: str, source: str = "") -> ExamAgentState:
    """Initialize the agent state."""
    return ExamAgentState(
        file_path=file_path,
        source=source or file_path,
        raw_markdown="",
        pages=[],
        status=ExtractionStatus.PENDING.value,
        questions=[],
        current_page=0,
        total_pages=0,
        pending_materials=[],
        pending_answers=[],
        last_question_id=0,
        confidence_threshold=0.6,
        low_confidence_questions=[],
        refinement_needed=False,
        extraction_report={},
        errors=[],
    )