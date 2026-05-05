from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..models import Textbook, Chapter, Section


class DoclingParser:
    name = "docling"

    def __init__(self, device: str = "cuda"):
        self.device = device
        self._converter = None

    def _get_converter(self):
        if self._converter is None:
            try:
                from docling.document_converter import DocumentConverter
                self._converter = DocumentConverter()
            except ImportError:
                raise ImportError(
                    "Docling not installed. Install with: pip install docling"
                )
        return self._converter

    def parse(self, pdf_path: str) -> Textbook:
        converter = self._get_converter()

        result = converter.convert(pdf_path)

        markdown = self._process_output(result)
        pdf_stem = Path(pdf_path).stem

        textbook_id = pdf_stem
        title = pdf_stem
        subject = "unknown"

        chapters = self._parse_markdown(markdown, textbook_id)

        total_words = sum(ch.word_count for ch in chapters)

        return Textbook(
            textbook_id=textbook_id,
            title=title,
            subject=subject,
            chapters=chapters,
            total_words=total_words,
            edition=None,
        )

    def _process_output(self, result) -> str:
        if isinstance(result, str):
            return result

        if isinstance(result, dict):
            return result.get("markdown", result.get("text", ""))

        if hasattr(result, "markdown"):
            return result.markdown

        if hasattr(result, "text"):
            return result.text

        return str(result)

    def _parse_markdown(self, markdown: str, textbook_id: str) -> list[Chapter]:
        blocks = self._split_by_headings(markdown)

        chapters = []
        for i, block in enumerate(blocks):
            if block["level"] == 1:
                chapter_id = f"{textbook_id}_ch_{i+1}"
                sections = self._extract_sections(block["content"], chapter_id)

                content_parts = [s.content for s in sections]
                content = "\n\n".join(content_parts)

                chapter = Chapter(
                    chapter_id=chapter_id,
                    title=block["title"],
                    level=1,
                    sections=sections,
                    content=content,
                    word_count=len(content.split()),
                    page_start=block.get("page_start"),
                    page_end=block.get("page_end"),
                )
                chapters.append(chapter)

        if not chapters:
            chapter = Chapter(
                chapter_id=f"{textbook_id}_ch_1",
                title="全文",
                level=1,
                sections=[],
                content=markdown,
                word_count=len(markdown.split()),
            )
            chapters.append(chapter)

        return chapters

    def _split_by_headings(self, markdown: str) -> list[dict]:
        lines = markdown.split("\n")
        blocks = []
        current_block = None

        for line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                if current_block:
                    blocks.append(current_block)

                level = len(heading_match.group(1))
                current_block = {
                    "level": level,
                    "title": heading_match.group(2).strip(),
                    "content": "",
                    "page_start": None,
                    "page_end": None,
                }
            elif current_block is not None:
                current_block["content"] += line + "\n"

        if current_block:
            blocks.append(current_block)

        return blocks

    def _extract_sections(self, content: str, parent_chapter_id: str) -> list[Section]:
        lines = content.split("\n")
        sections = []
        current_section = None
        section_num = 0

        for line in lines:
            subheading_match = re.match(r"^#{1,3}\s+(.+)$", line)
            if subheading_match:
                if current_section:
                    current_section["content"] = current_section["content"].strip()
                    sections.append(Section(**current_section))

                section_num += 1
                current_section = {
                    "section_id": f"{parent_chapter_id}_sec_{section_num}",
                    "title": subheading_match.group(1).strip(),
                    "parent_chapter_id": parent_chapter_id,
                    "content": "",
                    "word_count": 0,
                    "page_start": None,
                    "page_end": None,
                }
            elif current_section is not None:
                current_section["content"] += line + "\n"

        if current_section:
            current_section["content"] = current_section["content"].strip()
            current_section["word_count"] = len(
                current_section["content"].split()
            )
            sections.append(Section(**current_section))

        return sections
