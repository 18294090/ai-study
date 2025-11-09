"""Exam Parser - Extract questions from various document formats."""

__version__ = "0.1.0"

from .core import Question, LineBBox
from .parsers import parse_pdf, parse_docx, parse_image
from .utils import parse_path, export_results

__all__ = [
    "Question",
    "LineBBox",
    "parse_pdf",
    "parse_docx",
    "parse_image",
    "parse_path",
    "export_results",
]