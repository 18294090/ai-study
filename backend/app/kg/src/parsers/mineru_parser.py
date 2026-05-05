from __future__ import annotations

import re
from typing import Optional
from pathlib import Path

from ..models import Textbook, Chapter, Section


class MinerUParser:
    name = "mineru"

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from mineru import MagicPDF
                self._client = MagicPDF(device=self.device)
            except ImportError:
                raise ImportError(
                    "MinerU not installed. Install with: pip install mineru"
                )
        return self._client

    def parse(self, pdf_path: str) -> Textbook:
        client = self._get_client()
        pdf_bytes = Path(pdf_path).read_bytes()

        result = client.parse(pdf_bytes, parse_method="full")

        markdown = result.get("markdown", "")
        meta = result.get("meta", {})

        textbook_id = meta.get("textbook_id", Path(pdf_path).stem)
        title = meta.get("title", Path(pdf_path).stem)
        subject = meta.get("subject", "unknown")
        edition = meta.get("edition")

        chapters = self._parse_markdown(markdown, textbook_id)

        total_words = sum(ch.word_count for ch in chapters)

        return Textbook(
            textbook_id=textbook_id,
            title=title,
            subject=subject,
            chapters=chapters,
            total_words=total_words,
            edition=edition,
        )

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
