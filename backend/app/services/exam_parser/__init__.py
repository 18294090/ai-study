"""Exam Parser - Extract questions from documents with LLM assistance."""

from .core import Question, LineBBox
from .exam_analyzer import ExamAnalyzer, QuestionAnalysis, rule_based_type_detection
from .quality_evaluator import ExtractionQuality, evaluate_extraction, get_quality_report
from .parsers.pdf import parse_pdf, parse_markdown_to_questions, extract_questions_with_answers

__all__ = [
    "Question",
    "LineBBox",
    "ExamAnalyzer",
    "QuestionAnalysis",
    "rule_based_type_detection",
    "ExtractionQuality",
    "evaluate_extraction",
    "get_quality_report",
    "parse_pdf",
    "parse_markdown_to_questions",
    "extract_questions_with_answers",
]