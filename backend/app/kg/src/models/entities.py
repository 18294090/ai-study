from __future__ import annotations

from enum import Enum
from typing import Optional, List, Literal

from pydantic import BaseModel, Field


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
    confidence: float = Field(1.0, ge=0, le=1)
    layer: Literal["domain", "pedagogical", "diagnostic"] = "domain"


class JYTCompliantFields(BaseModel):
    jyt_code: Optional[str] = None
    jyt_category: Optional[str] = None


class Entity(EntityBase):
    layer: Literal["domain", "pedagogical", "diagnostic"] = "domain"
    type: EntityType
    description: Optional[str] = None
    latex: Optional[str] = None
    sympy_ast: Optional[str] = None
    community_id: Optional[str] = None
    skos_broader: Optional[str] = None
    skos_related: List[str] = []
    skos_exact_match: Optional[str] = None
    skos_close_match: Optional[str] = None
    curriculum_anchor: Optional[str] = None
    exam_scope: List[str] = []
    jyt: Optional[JYTCompliantFields] = None