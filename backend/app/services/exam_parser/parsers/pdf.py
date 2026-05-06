#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF parsing using MinerU with LLM-assisted question analysis."""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from ..core import Question, LineBBox

logger = logging.getLogger(__name__)


def parse_pdf(
    filepath: str,
    img_dir: str,
    layout_model=None,
    paddle_lang: str = "ch",
    force_ocr: bool = False,
) -> List[Question]:
    """Parse PDF using MinerU and extract questions with LLM assistance.

    Args:
        filepath: Path to the PDF file
        img_dir: Directory to save extracted images (unused, kept for API compatibility)
        layout_model: Unused, kept for API compatibility
        paddle_lang: Unused, kept for API compatibility
        force_ocr: Force OCR even if text is available

    Returns:
        List of parsed Question objects
    """
    try:
        from mineru import MagicPDF
    except ImportError:
        logger.error("MinerU not installed. Install with: pip install mineru")
        return []

    try:
        client = MagicPDF(device="cpu")
        pdf_bytes = Path(filepath).read_bytes()
        result = client.parse(pdf_bytes, parse_method="full")

        markdown = result.get("markdown", "")
        if not markdown:
            logger.warning("No markdown content extracted from PDF")
            return []

        # Extract images info from MinerU result
        images_info = result.get("images", []) or []

        lines = markdown.split("\n")
        questions = parse_markdown_to_questions(lines, source=filepath, images_info=images_info)

        # Evaluate extraction quality
        from ..quality_evaluator import evaluate_extraction, get_quality_report
        quality = evaluate_extraction(questions)

        if quality.score < 50:
            logger.warning(f"Low extraction quality: {quality.score:.1f}/100")
            for issue in quality.issues:
                logger.warning(f"  - {issue}")

        return questions

    except Exception as e:
        logger.error("Failed to parse PDF with MinerU: %s", e)
        return []


def parse_markdown_to_questions(
    lines: List[str],
    source: str,
    images_info: Optional[List[dict]] = None,
) -> List[Question]:
    """Parse markdown content to questions using hybrid approach.

    1. Rule-based extraction for structured content
    2. LLM-assisted analysis for ambiguous cases
    """
    from .utils import parse_text_to_questions as rule_based_parse
    from .exam_analyzer import ExamAnalyzer, rule_based_type_detection

    # First pass: rule-based extraction
    questions, _, _ = rule_based_parse(
        lines=lines,
        source=source,
        image_attach_queue=None,
    )

    # Second pass: LLM-assisted type detection for unknown types
    analyzer = ExamAnalyzer()

    for q in questions:
        if q.题型 == '未知' or q.题型 is None:
            # Try LLM analysis
            analysis = analyzer.analyze_question(q.内容)
            if analysis.confidence > 0.6:
                q.题型 = analysis.detected_type
            else:
                # Fall back to rule-based with options detection
                content = q.内容 or ""
                lines_content = content.split("\n")
                # Simple heuristic: if has multiple short lines starting with A/B/C, likely has options
                detected_type, confidence = rule_based_type_detection(content, lines_content)
                if confidence > 0.4:
                    q.题型 = detected_type

    return questions


def extract_questions_with_answers(markdown: str, source: str) -> Tuple[List[Question], List[str]]:
    """Extract questions and potential answers from markdown.

    Returns:
        Tuple of (questions, potential_answers)
    """
    from .exam_analyzer import ExamAnalyzer

    lines = markdown.split("\n")

    # Use rule-based for initial extraction
    from .utils import parse_text_to_questions
    questions, _, remaining = parse_text_to_questions(
        lines=lines,
        source=source,
        image_attach_queue=None,
    )

    # Analyze remaining text for answers
    potential_answers = []
    if remaining:
        # Try to extract answer patterns from remaining text
        analyzer = ExamAnalyzer()
        # Simple answer pattern detection
        import re
        answer_patterns = [
            r'答案[：:]\s*([A-H])',
            r'答[：:]\s*([A-H])',
            r'正确答案[：:]\s*([A-H])',
        ]
        for pattern in answer_patterns:
            matches = re.findall(pattern, remaining)
            potential_answers.extend(matches)

    return questions, potential_answers