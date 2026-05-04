from pydantic import BaseModel, Field
from typing import List, Optional

from app.kg.src.models.entities import EntityType, RelationType
from app.kg.src.models.textbook import Chapter
from app.kg.src.routing.structured_client import StructuredClient


class _Ent(BaseModel):
    name: str
    type: EntityType
    description: Optional[str] = None
    latex: Optional[str] = None


class _Tri(BaseModel):
    subject: _Ent
    predicate: RelationType
    object: _Ent
    confidence: float = Field(0.8, ge=0.0, le=1.0)


class DomainExtraction(BaseModel):
    triples: List[_Tri]


DOMAIN_SYSTEM = """你是一个学科知识抽取专家。从教材文本中抽取知识三元组。
要求：
- 仅抽取教材直接断言的知识，置信度 ≥ 0.8 才输出
- 公式必须保留 LaTeX 原文
- 因果与归类关系优先
- 严禁臆造原文未提及的事实"""


class DomainExtractor:
    def __init__(self, client: StructuredClient):
        self.client = client

    def extract(self, chapter: Chapter, book_context: str) -> DomainExtraction:
        return self.client.extract(
            system=DOMAIN_SYSTEM,
            user=f"<chapter id={chapter.chapter_id} title='{chapter.title}'>\n{chapter.content}\n</chapter>",
            schema=DomainExtraction,
            cached_prefix=book_context,
        )