from pydantic import BaseModel
from typing import List

from app.kg.src.models.diagnostic import QMatrixEntry
from app.kg.src.routing.structured_client import StructuredClient


class SkillMappingResult(BaseModel):
    q_matrix_entries: List[QMatrixEntry]


SKILL_MAPPER_SYSTEM = """你是一个技能映射专家。根据题目和知识点列表，生成 Q-matrix 草稿。
要求：
- 为每个题目标注所需技能
- 提供技能权重（0-1，越高越关键）
- 仅标注题目明确涉及的技能"""


class SkillMapper:
    def __init__(self, client: StructuredClient):
        self.client = client

    def map_skills(self, concepts: List[str], item_text: str) -> SkillMappingResult:
        return self.client.extract(
            system=SKILL_MAPPER_SYSTEM,
            user=f"<concepts>\n{', '.join(concepts)}\n</concepts>\n<item>\n{item_text}\n</item>",
            schema=SkillMappingResult,
            cached_prefix=None,
        )