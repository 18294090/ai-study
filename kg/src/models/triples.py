from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional

from .entities import Entity, RelationType, TextbookAnchor


class KnowledgeTriple(BaseModel):
    subject: Entity
    predicate: RelationType
    object: Entity
    confidence: float = Field(1.0, ge=0, le=1)
    anchor: Optional[TextbookAnchor] = None
    extracted_by: Optional[str] = None
    verified_by: Optional[str] = None

    def dedup_key(self) -> tuple:
        return (
            self.subject.name,
            self.subject.type,
            self.predicate,
            self.object.name,
            self.object.type,
        )
