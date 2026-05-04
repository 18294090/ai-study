from __future__ import annotations
from typing import List, Any, Optional
import os
import re
import json

from .types import Citation, GenerationResult


SYSTEM_PROMPT = """你是一个知识图谱问答助手。

规则：
- 必须引用相关KG节点，使用格式：{{citation: node_id}}
- 每个声明都需要有对应的citation
- 仅基于提供的证据回答，禁止臆造
- 回答需要可解释，附上KG路径
- JSON响应格式：{"answer": "...", "citations": [{"kg_node_id": "...", "excerpt": "..."}], "kg_paths": ["path1", "path2"]}"""


class Generator:
    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model

    def generate(
        self,
        question: str,
        contexts: List[Any],
        model: str = None,
    ) -> GenerationResult:
        from openai import OpenAI

        context_texts = self._format_contexts(contexts)
        user_prompt = f"问题：{question}\n\n证据：\n{context_texts}"

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=model or self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return self._parse_response(content)

    def _format_contexts(self, contexts: List[Any]) -> str:
        lines = []
        for i, ctx in enumerate(contexts):
            if hasattr(ctx, "text"):
                lines.append(f"[{i}] (chunk) {ctx.text[:500]}")
            elif hasattr(ctx, "name"):
                neighbor_text = " ".join([n.target_name for n in getattr(ctx, "neighbors", [])])
                lines.append(f"[{i}] (entity) {ctx.name}: {getattr(ctx, 'description', '') or ''} | neighbors: {neighbor_text}")
            elif hasattr(ctx, "summary_text"):
                lines.append(f"[{i}] (community) {ctx.summary_text[:500]}")
        return "\n".join(lines) if lines else "无相关证据"

    def _parse_response(self, content: str) -> GenerationResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            citation_matches = re.findall(r"\{\{citation:\s*([^}]+)\}\}", content)
            return GenerationResult(
                answer=content,
                citations=[Citation(kg_node_id=cid, excerpt="") for cid in citation_matches],
                kg_paths=[],
            )

        citations = []
        for c in data.get("citations", []):
            citations.append(Citation(
                kg_node_id=c.get("kg_node_id", ""),
                chapter_id=c.get("chapter_id"),
                paragraph_offset=c.get("paragraph_offset"),
                excerpt=c.get("excerpt", ""),
            ))

        return GenerationResult(
            answer=data.get("answer", ""),
            citations=citations,
            kg_paths=data.get("kg_paths", []),
        )