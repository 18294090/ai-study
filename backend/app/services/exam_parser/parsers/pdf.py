#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PDF parsing using MinerU for unified document parsing."""

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
    """Parse PDF using MinerU and extract questions.

    This function unifies all PDF parsing through MinerU.

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

        from ..utils import parse_text_to_questions
        lines = markdown.split("\n")
        questions, _, _ = parse_text_to_questions(
            lines=lines,
            source=filepath,
            image_attach_queue=None,
        )

        return questions

    except Exception as e:
        logger.error("Failed to parse PDF with MinerU: %s", e)
        return []