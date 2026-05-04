from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class Section(BaseModel):
    section_id: str
    title: str
    parent_chapter_id: str
    content: str
    word_count: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class Chapter(BaseModel):
    chapter_id: str
    title: str
    level: int = 1
    parent_id: Optional[str] = None
    sections: List[Section] = []
    content: str
    word_count: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class Textbook(BaseModel):
    textbook_id: str
    title: str
    subject: str
    chapters: List[Chapter]
    total_words: int
    edition: Optional[str] = None
