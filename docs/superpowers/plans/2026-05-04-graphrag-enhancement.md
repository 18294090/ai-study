# GraphRAG Enhancement: Two-Step CoT + 4-Signal Relevance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强 GraphRAG：Generator 改为两步 CoT（分析→生成），Reranker 引入 4-signal 图相关性模型。

**Architecture:** 替换现有 generator.py 和 reranker.py，types.py 新增 AnalysisResult，graphrag_service.py 调整调用顺序。

**Tech Stack:** LangGraph, Neo4j, Cohere, OpenAI

---

## File Map

### Modified Files
- `backend/app/kg/agents/graphrag/types.py` — 新增 `AnalysisResult`
- `backend/app/kg/agents/graphrag/generator.py` — 两步 CoT
- `backend/app/kg/agents/graphrag/reranker.py` — 4-signal + Cohere 混合
- `backend/app/kg/agents/graphrag_service.py` — 调整调用顺序

---

## Task 1: Add AnalysisResult type

**Files:**
- Modify: `backend/app/kg/agents/graphrag/types.py`

- [ ] **Step 1: Read current types.py**

Read the file to find the right location to add AnalysisResult.

- [ ] **Step 2: Add AnalysisResult after GenerationResult**

Add this class before `VerificationResult`:

```python
class AnalysisResult(BaseModel):
    key_entities: List[str] = Field(default_factory=list)
    connections_to_existing: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    structure_recommendations: str = ""
    reasoning: str = ""
```

- [ ] **Step 3: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.graphrag.types import AnalysisResult; print('AnalysisResult OK')"
```

- [ ] **Step 4: Commit**

---

## Task 2: Rewrite Generator with Two-Step CoT

**Files:**
- Modify: `backend/app/kg/agents/graphrag/generator.py`

- [ ] **Step 1: Read current generator.py**

Read the current implementation to understand its interface.

- [ ] **Step 2: Replace with two-step CoT implementation**

The new `Generator` class keeps the same public interface but changes `_analyze` then `_generate`:

```python
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
```

- [ ] **Step 3: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.graphrag.generator import Generator, AnalysisResult; print('Two-step Generator OK')"
```

- [ ] **Step 4: Commit**

---

## Task 3: Rewrite Reranker with 4-Signal Relevance

**Files:**
- Modify: `backend/app/kg/agents/graphrag/reranker.py`

- [ ] **Step 1: Read current reranker.py**

- [ ] **Step 2: Replace with 4-signal implementation**

The new `Reranker` class computes 4 signals from Neo4j graph, then blends with Cohere rerank score.

```python
from __future__ import annotations
from typing import List, Union, Dict, Any, Optional
from pydantic import BaseModel
import os


class RerankResult(BaseModel):
    index: int
    document: Union[str, Dict[str, Any]]
    relevance_score: float


class FourSignalResult(BaseModel):
    direct_link_score: float
    source_overlap_score: float
    adamic_adar_score: float
    type_affinity_score: float
    combined_score: float


SIGNAL_WEIGHTS = {
    "direct_link": 3.0,
    "source_overlap": 4.0,
    "adamic_adar": 1.5,
    "type_affinity": 1.0,
}

RERANK_BLEND = 0.4  # Cohere weight
GRAPH_BLEND = 0.6  # 4-signal graph weight


class Reranker:
    def __init__(
        self,
        api_key: str = None,
        model: str = "rerank-v3",
        neo4j_driver=None,
    ):
        self.api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self.model = model
        self.neo4j_driver = neo4j_driver
        self._client = None

    def _get_cohere_client(self):
        if self._client is None:
            import cohere
            self._client = cohere.Client(self.api_key)
        return self._client

    def rerank(
        self,
        query: str,
        documents: List[Union[str, Dict[str, Any]]],
        top_n: int = 10,
    ) -> List[RerankResult]:
        if not documents:
            return []

        client = self._get_cohere_client()
        doc_texts = [d if isinstance(d, str) else d.get("text", str(d)) for d in documents]

        response = client.rerank(
            query=query,
            documents=doc_texts,
            top_n=top_n,
            model=self.model,
            return_documents=False,
        )

        results = []
        for r in response.results:
            results.append(RerankResult(
                index=r.index,
                document=documents[r.index],
                relevance_score=r.relevance_score,
            ))
        return results

    def rerank_hybrid(
        self,
        query: str,
        vector_results: List[Any],
        kg_entities: List[Any],
        seed_node_ids: List[str] = None,
        top_n: int = 10,
    ) -> List[Any]:
        all_docs = []
        doc_sources = []

        for v in vector_results:
            all_docs.append({"text": v.text, "id": v.chunk_id, "type": "vector"})
            doc_sources.append(("vector", v))

        for e in kg_entities:
            neighbors_text = " ".join([n.target_name for n in e.neighbors])
            all_docs.append({"text": f"{e.name}: {e.description or ''} {neighbors_text}", "id": e.entity_id, "type": "kg"})
            doc_sources.append(("kg", e))

        if not all_docs:
            return []

        reranked = self.rerank(query, all_docs, top_n=len(all_docs))

        rerank_scores = {r.index: r.relevance_score for r in reranked}

        graph_scores = self._compute_graph_signals(
            doc_sources,
            seed_node_ids or [],
        )

        final_scores = []
        for i, (source_type, source_obj) in enumerate(doc_sources):
            rerank_s = rerank_scores.get(i, 0.0)
            graph_s = graph_scores.get(i, 0.0)
            combined = RERANK_BLEND * rerank_s + GRAPH_BLEND * graph_s
            final_scores.append((combined, source_type, source_obj, rerank_s, graph_s))

        final_scores.sort(key=lambda x: x[0], reverse=True)
        return [(source_type, source_obj, final_score, rerank_s, graph_s)
                for final_score, source_type, source_obj, rerank_s, graph_s in final_scores[:top_n]]

    def _compute_graph_signals(
        self,
        doc_sources: List[tuple],
        seed_node_ids: List[str],
    ) -> Dict[int, float]:
        if self.neo4j_driver is None:
            return {i: 0.0 for i in range(len(doc_sources))}

        doc_ids = [src[1].entity_id if src[0] == "kg" else src[1].chunk_id for src in doc_sources]
        doc_types = [src[1].entity_type if src[0] == "kg" else "chunk" for src in doc_sources]
        doc_source_files = [getattr(src[1], "source_file", None) for src in doc_sources]

        scores = {}
        for i in range(len(doc_sources)):
            s = SIGNAL_WEIGHTS["type_affinity"]
            if doc_types[i] in ("concept", "entity") and seed_node_ids:
                for sid in seed_node_ids:
                    s += SIGNAL_WEIGHTS["direct_link"] * self._get_link_strength(doc_ids[i], sid, doc_types[i])
            for j in range(len(doc_sources)):
                if i != j and doc_source_files[i] and doc_source_files[i] == doc_source_files[j]:
                    s += SIGNAL_WEIGHTS["source_overlap"]
            if seed_node_ids:
                s += SIGNAL_WEIGHTS["adamic_adar"] * self._get_adamic_adar(doc_ids[i], seed_node_ids)
            scores[i] = s

        max_s = max(scores.values()) if scores else 1.0
        return {k: v / max_s for k, v in scores.items()}

    def _get_link_strength(self, node_a: str, node_b: str, node_type: str) -> float:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (a)-[r]->(b) WHERE a.id = $a AND b.id = $b RETURN count(r) as c",
                    a=node_a, b=node_b
                )
                data = result.data()
                return float(data[0]["c"]) if data else 0.0
        except Exception:
            return 0.0

    def _get_adamic_adar(self, node: str, seed_nodes: List[str]) -> float:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (n)-[r1]-(mid)-[r2]-(seed) "
                    "WHERE n.id = $node AND seed.id IN $seeds AND mid <> n AND mid <> seed "
                    "RETURN count(DISTINCT mid) as common_neighbors",
                    node=node, seeds=seed_nodes
                )
                data = result.data()
                common = float(data[0]["common_neighbors"]) if data else 0.0
                return 1.0 / (common + 1.0)
        except Exception:
            return 0.0
```

- [ ] **Step 3: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.graphrag.reranker import Reranker, FourSignalResult; print('4-signal Reranker OK')"
```

- [ ] **Step 4: Commit**

---

## Task 4: Update GraphRAGService to pass neo4j_driver to Reranker

**Files:**
- Modify: `backend/app/kg/agents/graphrag_service.py`

- [ ] **Step 1: Read current graphrag_service.py**

Find the line where Reranker is instantiated.

- [ ] **Step 2: Pass neo4j_driver to Reranker**

Change:
```python
self.reranker = Reranker(api_key=self.api_key)
```
To:
```python
self.reranker = Reranker(api_key=self.api_key, neo4j_driver=neo4j_driver)
```

- [ ] **Step 3: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.graphrag_service import GraphRAGService; print('GraphRAGService with 4-signal OK')"
```

- [ ] **Step 4: Commit**

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| AnalysisResult type | Task 1 |
| Two-step CoT Generator | Task 2 |
| 4-signal relevance model | Task 3 |
| Neo4j driver passed to Reranker | Task 4 |

All requirements covered. No placeholders found. Types consistent across tasks.

---

**Plan complete.**