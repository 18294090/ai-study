from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class EntityType(str, Enum):
    CONCEPT = "concept"
    FORMULA = "formula"
    THEOREM = "theorem"
    PERSON = "person"
    EVENT = "event"
    LOCATION = "location"
    WORK = "work"
    TIME = "time"
    DATASET = "dataset"


class RelationType(str, Enum):
    IS_A = "is_a"
    PART_OF = "part_of"
    CAUSES = "causes"
    EQUIVALENT_TO = "equivalent_to"
    GENERALIZES = "generalizes"
    CONTRADICTS = "contradicts"
    APPLIES_TO = "applies_to"
    REQUIRES = "requires"
    BEFORE = "before"
    AFTER = "after"
    SIMILAR_TO = "similar_to"
    DEFINED_BY = "defined_by"
    EXAMPLE_OF = "example_of"


class TextbookAnchor(BaseModel):
    textbook_id: str
    chapter_id: str
    paragraph_offset: int = 0
    page: Optional[int] = None


class EntityBase(BaseModel):
    id: str
    name: str
    anchor: Optional[TextbookAnchor] = None
    confidence: float = 1.0
    layer: str = "domain"


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