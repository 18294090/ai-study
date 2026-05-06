from typing import Callable, Optional
from dataclasses import dataclass

from pydantic import BaseModel

from src.models.entities import Entity


@dataclass
class VerificationResult:
    is_same: bool
    reason: str


class _VerificationSchema(BaseModel):
    """Structured output schema for LLM-based entity co-reference verification."""
    is_same: bool
    reason: str
    confidence: float  # 0.0 – 1.0


_VERIFY_SYSTEM = """你是一个知识图谱实体消歧专家。
判断以下两个实体是否指同一概念，返回 JSON。
规则：
- 同一领域、同义或缩写关系 → is_same=true
- 同名但含义不同（如同名公式 vs 同名人物）→ is_same=false
- confidence 反映你的把握程度（0.0~1.0）"""


class VerifierAgent:
    def __init__(self, llm_fn: Callable[[str], str], structured_client=None):
        """``structured_client`` is preferred (StructuredClient / AnthropicStructuredClient);
        ``llm_fn`` is kept as a fallback for callers that pass a plain text callable."""
        self.llm_fn = llm_fn
        self.structured_client = structured_client

    def verify(self, entity1: Entity, entity2: Entity) -> VerificationResult:
        if self.structured_client is not None:
            return self._verify_structured(entity1, entity2)
        return self._verify_text(entity1, entity2)

    # ------------------------------------------------------------------
    # Structured path (preferred)
    # ------------------------------------------------------------------
    def _verify_structured(self, entity1: Entity, entity2: Entity) -> VerificationResult:
        user = self._build_user_content(entity1, entity2)
        try:
            result: _VerificationSchema = self.structured_client.extract(
                system=_VERIFY_SYSTEM,
                user=user,
                schema=_VerificationSchema,
            )
            return VerificationResult(is_same=result.is_same, reason=result.reason)
        except Exception:
            # Gracefully fall back to text path on extraction failure
            return self._verify_text(entity1, entity2)

    # ------------------------------------------------------------------
    # Text fallback path
    # ------------------------------------------------------------------
    def _verify_text(self, entity1: Entity, entity2: Entity) -> VerificationResult:
        prompt = _VERIFY_SYSTEM + "\n\n" + self._build_user_content(entity1, entity2)
        response = self.llm_fn(prompt)
        return self._parse_text_response(response)

    def _build_user_content(self, entity1: Entity, entity2: Entity) -> str:
        def _fmt(e: Entity) -> str:
            parts = [f"名称: {e.name}"]
            t = getattr(e, 'type', None)
            if t:
                parts.append(f"类型: {t.value if hasattr(t, 'value') else t}")
            desc = getattr(e, 'description', None)
            if desc:
                parts.append(f"描述: {desc[:300]}")
            return "; ".join(parts)

        return f"实体A: {_fmt(entity1)}\n实体B: {_fmt(entity2)}"

    def _parse_text_response(self, response: str) -> VerificationResult:
        """Robust text-response parser: checks multiple affirmative/negative patterns."""
        r = response.strip()
        affirmative = ("是的", "是同一", "是相同", "yes", "true", "same", "相同", "同一")
        negative = ("不是", "不同", "no", "false", "different", "非同")
        r_lower = r.lower()
        for token in affirmative:
            if token in r_lower:
                return VerificationResult(is_same=True, reason=r)
        for token in negative:
            if token in r_lower:
                return VerificationResult(is_same=False, reason=r)
        # Default conservative: treat ambiguous as not-same
        return VerificationResult(is_same=False, reason=r)