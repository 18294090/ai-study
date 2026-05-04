from __future__ import annotations

from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel

from .entities import EntityBase, EntityType


class BloomLevel(str, Enum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class LearningObjective(BaseModel):
    description: str
    target_concepts: List[str]
    bloom_level: BloomLevel
    dok_level: int
    estimated_minutes: int


class Misconception(BaseModel):
    description: str
    related_concepts: List[str]
    example_wrong_answers: List[str] = []


class CurriculumStandardNode(BaseModel):
    standard_id: str
    subject: str
    grade_band: str
    content_requirement: str
    bloom_required: BloomLevel
    exam_scope: List[str]
    exam_weight: Optional[float] = None
    wikidata_qid: Optional[str] = None