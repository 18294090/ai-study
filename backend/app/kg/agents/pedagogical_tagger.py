from pydantic import BaseModel
from typing import List

from src.models.pedagogical import BloomLevel
from src.models.textbook import Chapter
from src.routing.structured_client import StructuredClient


class _LearningObjective(BaseModel):
    description: str
    target_concepts: List[str]
    bloom_level: BloomLevel
    dok_level: int
    estimated_minutes: int


class _Misconception(BaseModel):
    description: str
    related_concepts: List[str]
    example_wrong_answers: List[str] = []


class PedagogicalExtraction(BaseModel):
    learning_objectives: List[_LearningObjective]
    misconceptions: List[_Misconception]
    bloom_levels: List[str]


PEDAGOGICAL_SYSTEM = """你是一个教学标注专家。从教材文本中标注教学相关元素。
要求：
- learning_objectives: 描述学生完成本章后应掌握的知识与技能
- misconceptions: 学生常见误解，仅当教材明确提及时标注
- bloom_levels: 本章涉及的认知层次"""


class PedagogicalTagger:
    def __init__(self, client: StructuredClient):
        self.client = client

    def tag(self, chapter: Chapter, book_context: str) -> PedagogicalExtraction:
        return self.client.extract(
            system=PEDAGOGICAL_SYSTEM,
            user=f"<chapter id={chapter.chapter_id} title='{chapter.title}'>\n{chapter.content}\n</chapter>",
            schema=PedagogicalExtraction,
            cached_prefix=book_context,
        )