from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Intent(str, Enum):
    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    EXPLANATORY = "explanatory"
    META = "meta"


class IntentResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class TextbookAnchor(BaseModel):
    textbook_id: Optional[str] = None
    chapter_id: Optional[str] = None
    paragraph_offset: Optional[int] = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    community_id: Optional[str] = None
    textbook_anchor: Optional[TextbookAnchor] = None


class EntityEdge(BaseModel):
    target_id: str
    target_name: str
    relation_type: str


class RetrievedEntity(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    description: Optional[str] = None
    neighbors: List[EntityEdge] = Field(default_factory=list)
    score: float = 0.0


class CommunitySummary(BaseModel):
    level: int
    community_id: str
    core_concepts: List[str]
    key_relationships: List[str]
    typical_applications: List[str]
    summary_text: str


class Citation(BaseModel):
    kg_node_id: str
    chapter_id: Optional[str] = None
    paragraph_offset: Optional[int] = None
    excerpt: str = ""


class GenerationResult(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    kg_paths: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class VerificationResult(BaseModel):
    is_valid: bool
    has_sufficient_citations: bool = True
    has_hallucination: bool = False
    is_within_scope: bool = True
    feedback: str = ""
    issues: List[str] = Field(default_factory=list)


class GraphRAGResult(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    kg_paths: List[str] = Field(default_factory=list)
    intent: Intent
    retrieval_type: str  # "hybrid" | "community"
    verification: Optional[VerificationResult] = None