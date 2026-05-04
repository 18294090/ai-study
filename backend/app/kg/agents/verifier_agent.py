from typing import Callable
from dataclasses import dataclass

from src.models.entities import Entity


@dataclass
class VerificationResult:
    is_same: bool
    reason: str


class VerifierAgent:
    def __init__(self, llm_fn: Callable[[str], str]):
        self.llm_fn = llm_fn

    def verify(self, entity1: Entity, entity2: Entity) -> VerificationResult:
        prompt = self._build_prompt(entity1, entity2)
        response = self.llm_fn(prompt)
        return self._parse_response(response)

    def _build_prompt(self, entity1: Entity, entity2: Entity) -> str:
        return (
            f"以下两个实体是否指同一概念？请回答是或否，并说明理由。\n\n"
            f"实体1: {entity1.name} (type: {getattr(entity1, 'type', 'unknown')})\n"
            f"实体2: {entity2.name} (type: {getattr(entity2, 'type', 'unknown')})\n"
        )

    def _parse_response(self, response: str) -> VerificationResult:
        response_lower = response.lower().strip()
        if response_lower.startswith('是') or response_lower.startswith('yes'):
            return VerificationResult(is_same=True, reason=response)
        return VerificationResult(is_same=False, reason=response)