from __future__ import annotations
from typing import List, Any, Optional
import os
import json

from .types import GenerationResult, VerificationResult


SYSTEM_PROMPT = """你是一个事实核查专家。验证AI回答是否：
1. 有充分的citation支撑（每个声明都有对应引用）
2. 没有幻觉（引用的节点在证据中真实存在）
3. 在检索范围内回答（没有超出证据的推断）

回答JSON格式：
{
  "is_valid": true/false,
  "has_sufficient_citations": true/false,
  "has_hallucination": true/false,
  "is_within_scope": true/false,
  "feedback": "简要反馈",
  "issues": ["问题1", "问题2"]
}"""


class SelfRAGVerifier:
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model

    def verify(
        self,
        question: str,
        generation: GenerationResult,
        retrieval_contexts: List[Any],
    ) -> VerificationResult:
        if not generation.citations:
            return VerificationResult(
                is_valid=False,
                has_sufficient_citations=False,
                has_hallucination=False,
                is_within_scope=True,
                feedback="No citations provided",
                issues=["No citations in answer"],
            )

        citation_text = "\n".join([
            f"- {c.kg_node_id}: {c.excerpt}" for c in generation.citations
        ])

        context_text = "\n".join([
            self._ctx_to_text(c) for c in retrieval_contexts
        ]) if retrieval_contexts else "无可用证据"

        user_prompt = f"""问题：{question}

回答：{generation.answer}

Citations：
{citation_text}

证据：
{context_text}

请验证以上回答。"""

        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return self._parse_result(content)

    def _ctx_to_text(self, ctx: Any) -> str:
        if hasattr(ctx, "text"):
            return f"[chunk] {ctx.text[:300]}"
        elif hasattr(ctx, "name"):
            return f"[entity] {ctx.name}"
        elif hasattr(ctx, "summary_text"):
            return f"[community] {ctx.summary_text[:300]}"
        return str(ctx)

    def _parse_result(self, content: str) -> VerificationResult:
        try:
            data = json.loads(content)
            return VerificationResult(
                is_valid=data.get("is_valid", False),
                has_sufficient_citations=data.get("has_sufficient_citations", True),
                has_hallucination=data.get("has_hallucination", False),
                is_within_scope=data.get("is_within_scope", True),
                feedback=data.get("feedback", ""),
                issues=data.get("issues", []),
            )
        except json.JSONDecodeError:
            return VerificationResult(
                is_valid=False,
                has_sufficient_citations=False,
                has_hallucination=True,
                is_within_scope=False,
                feedback="Failed to parse verification response",
                issues=["JSON parse failed"],
            )