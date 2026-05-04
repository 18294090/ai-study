from __future__ import annotations
from typing import List, Any, Optional
import os
import re
import json

from .types import Citation, GenerationResult, AnalysisResult


ANALYSIS_SYSTEM = """你是一个知识分析专家。分析检索到的上下文，理解：
1. 关键实体和概念有哪些
2. 与已有知识库的关联（哪些节点可能已存在）
3. 与已有知识的矛盾或分歧
4. 回答应该采用什么结构

输出JSON格式：
{
  "key_entities": ["entity1", "entity2"],
  "connections_to_existing": ["concept_x", "theorem_y"],
  "contradictions": [],
  "structure_recommendations": "建议的回答结构",
  "reasoning": "分析过程"
}"""


GENERATION_SYSTEM = """你是一个知识图谱问答助手。

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
        model = model or self.model

        analysis = self._analyze(question, contexts, model)

        generation = self._generate(question, contexts, analysis, model)

        return generation

    def _analyze(
        self,
        question: str,
        contexts: List[Any],
        model: str,
    ) -> AnalysisResult:
        from openai import OpenAI

        context_texts = self._format_contexts(contexts)
        user_prompt = f"问题：{question}\n\n证据：\n{context_texts}\n\n请分析以上证据，为生成答案做准备。"

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return self._parse_analysis(content)

    def _generate(
        self,
        question: str,
        contexts: List[Any],
        analysis: AnalysisResult,
        model: str,
    ) -> GenerationResult:
        from openai import OpenAI

        context_texts = self._format_contexts(contexts)

        analysis_context = f"""分析结果：
关键实体：{', '.join(analysis.key_entities)}
关联概念：{', '.join(analysis.connections_to_existing)}
矛盾点：{', '.join(analysis.contradictions) if analysis.contradictions else '无'}
建议结构：{analysis.structure_recommendations}

证据：
{context_texts}"""

        user_prompt = f"问题：{question}\n\n{analysis_context}"

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": GENERATION_SYSTEM},
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

    def _parse_analysis(self, content: str) -> AnalysisResult:
        try:
            data = json.loads(content)
            return AnalysisResult(
                key_entities=data.get("key_entities", []),
                connections_to_existing=data.get("connections_to_existing", []),
                contradictions=data.get("contradictions", []),
                structure_recommendations=data.get("structure_recommendations", ""),
                reasoning=data.get("reasoning", ""),
            )
        except json.JSONDecodeError:
            return AnalysisResult(reasoning="Analysis parse failed, proceeding without analysis")

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