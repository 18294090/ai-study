from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel

from .entities import EntityBase


class Skill(EntityBase):
    layer: Literal["domain", "pedagogical", "diagnostic"] = "diagnostic"
    parent_skill: Optional[str] = None
    mastery_threshold: float = 0.8


class QMatrixEntry(BaseModel):
    item_id: str
    required_skills: List[str]
    weights: List[float]
