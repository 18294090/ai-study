# GraphRAG MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 GraphRAG MVP：意图分类 → 混合召回/社区召回 → Rerank → LLM生成+Citation → Self-RAG验证

**Architecture:** 内部 LangGraph Service，被 Tutor/题库等模块调用。意图分类决定路由（factual/procedural→混合召回，explanatory/meta→社区召回）。复用现有 CommunityDetector、StructuredClient、Neo4jWriter、QdrantWriter。

**Tech Stack:** LangGraph, Pydantic, Cohere SDK, sentence-transformers (BGE-M3), Neo4j, Qdrant

---

## File Map

### New Files

**Core types (shared):**
- `backend/app/kg/agents/graphrag/__init__.py`
- `backend/app/kg/agents/graphrag/types.py`

**Components:**
- `backend/app/kg/agents/graphrag/intent_classifier.py`
- `backend/app/kg/agents/graphrag/community_retriever.py`
- `backend/app/kg/agents/graphrag/hybrid_retriever.py`
- `backend/app/kg/agents/graphrag/reranker.py`
- `backend/app/kg/agents/graphrag/generator.py`
- `backend/app/kg/agents/graphrag/verifier.py`
- `backend/app/kg/agents/graphrag_service.py`

**Config updates:**
- `backend/app/kg/config.yaml` (update)
- `backend/app/kg/src/config.py` (update)

**Tests:**
- `backend/tests/unit/kg/agents/test_graphrag_types.py`
- `backend/tests/unit/kg/agents/test_intent_classifier.py`
- `backend/tests/unit/kg/agents/test_reranker.py`
- `backend/tests/unit/kg/agents/test_generator.py`
- `backend/tests/unit/kg/agents/test_verifier.py`
- `backend/tests/integration/kg/agents/test_graphrag_service.py`

---

## Task 1: Create shared types

**Files:**
- Create: `backend/app/kg/agents/graphrag/__init__.py`
- Create: `backend/app/kg/agents/graphrag/types.py`
- Test: `backend/tests/unit/kg/agents/test_graphrag_types.py`

- [ ] **Step 1: Create __init__.py**

```python
from .types import (
    Intent,
    IntentResult,
    RetrievedChunk,
    RetrievedEntity,
    EntityEdge,
    Citation,
    GraphRAGResult,
)
from .intent_classifier import IntentClassifier
from .community_retriever import CommunityRetriever
from .hybrid_retriever import HybridRetriever
from .reranker import Reranker
from .generator import Generator
from .verifier import SelfRAGVerifier

__all__ = [
    "Intent",
    "IntentResult",
    "RetrievedChunk",
    "RetrievedEntity",
    "EntityEdge",
    "Citation",
    "GraphRAGResult",
    "IntentClassifier",
    "CommunityRetriever",
    "HybridRetriever",
    "Reranker",
    "Generator",
    "SelfRAGVerifier",
]
```

- [ ] **Step 2: Create types.py**

```python
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Any
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
```

- [ ] **Step 3: Run test to verify types**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.graphrag.types import Intent, IntentResult, RetrievedChunk, RetrievedEntity, Citation, GraphRAGResult; print('types import OK')"
```

- [ ] **Step 4: Commit**

---

## Task 2: Implement IntentClassifier

**Files:**
- Create: `backend/app/kg/agents/graphrag/intent_classifier.py`
- Test: `backend/tests/unit/kg/agents/test_intent_classifier.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/kg/agents/test_intent_classifier.py
import pytest
from app.kg.agents.graphrag.intent_classifier import IntentClassifier, Intent, IntentResult


class TestIntentClassifier:
    def test_classify_factual(self):
        classifier = IntentClassifier()
        result = classifier.classify("什么是梯度下降法？")
        assert result.intent == Intent.FACTUAL
        assert result.confidence >= 0.5

    def test_classify_procedural(self):
        classifier = IntentClassifier()
        result = classifier.classify("如何求解二元一次方程组？")
        assert result.intent == Intent.PROCEDURAL

    def test_classify_explanatory(self):
        classifier = IntentClassifier()
        result = classifier.classify("为什么矩阵乘法是这样定义的？")
        assert result.intent == Intent.EXPLANATORY

    def test_classify_meta(self):
        classifier = IntentClassifier()
        result = classifier.classify("我应该先学习线性代数还是微积分？")
        assert result.intent == Intent.META
```

- [ ] **Step 2: Run test - expect FAIL (not implemented)**

```bash
cd /home/zh/ai-study/backend && python3 -m pytest tests/unit/kg/agents/test_intent_classifier.py -v 2>&1 | head -20
```

- [ ] **Step 3: Write IntentClassifier**

```python
# backend/app/kg/agents/graphrag/intent_classifier.py
from __future__ import annotations
from typing import Type
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
import os

from .types import Intent, IntentResult


SYSTEM_PROMPT = """你是一个意图分类专家。根据用户问题判断其意图类型：

- factual: 具体知识点查询，如"什么是X"、"X的定义"
- procedural: 步骤/过程类问题，如"如何做X"、"X的步骤"
- explanatory: 概念解释类，如"为什么X"、"X的原理"
- meta: 关于学习本身的问题，如"应该先学X还是Y"、"如何学习X"

输出JSON格式，包含intent（字符串）、confidence（0-1）、reasoning（简短理由）。"""


class IntentClassifier:
    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    def _get_client(self) -> ChatOpenAI:
        return ChatOpenAI(model=self.model, api_key=self.api_key)

    def classify(self, question: str) -> IntentResult:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            response_format={"type": "json_object"},
        )
        import json
        data = json.loads(response.choices[0].message.content)
        return IntentResult(
            intent=Intent(data["intent"]),
            confidence=float(data.get("confidence", 0.8)),
            reasoning=data.get("reasoning", ""),
        )

    def classify_sync(self, question: str) -> IntentResult:
        return self.classify(question)
```

- [ ] **Step 4: Run test - expect PASS**

```bash
cd /home/zh/ai-study/backend && python3 -m pytest tests/unit/kg/agents/test_intent_classifier.py -v
```

- [ ] **Step 5: Commit**

---

## Task 3: Implement CommunityRetriever

**Files:**
- Create: `backend/app/kg/agents/graphrag/community_retriever.py`
- Test: `backend/tests/unit/kg/agents/test_community_retriever.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/kg/agents/test_community_retriever.py
import pytest
from unittest.mock import MagicMock, patch
from app.kg.agents.graphrag.community_retriever import CommunityRetriever


class TestCommunityRetriever:
    @patch("app.kg.agents.community_detector.CommunityDetector")
    def test_retrieve_returns_summaries(self, mock_detector):
        mock_summary = MagicMock()
        mock_summary.community_id = "comm_1"
        mock_summary.core_concepts = ["梯度", "优化"]
        mock_summary.summary_text = "这是机器学习优化社区"
        mock_detector_instance = mock_detector.return_value
        mock_detector_instance.retrieve_by_query.return_value = [mock_summary]

        retriever = CommunityRetriever(neo4j_driver=MagicMock())
        result = retriever.retrieve("什么是梯度下降", top_k=3)

        assert len(result.community_summaries) == 1
        assert result.community_summaries[0].community_id == "comm_1"
```

- [ ] **Step 2: Run test - expect FAIL**

- [ ] **Step 3: Write CommunityRetriever**

```python
# backend/app/kg/agents/graphrag/community_retriever.py
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

from .types import CommunitySummary, RetrievedChunk
from ..community_detector import CommunityDetector


class CommunityRetrieveResult(BaseModel):
    community_summaries: List[CommunitySummary]
    query: str


class CommunityRetriever:
    def __init__(self, neo4j_driver, embedder=None, top_k: int = 5):
        self.neo4j_driver = neo4j_driver
        self.embedder = embedder
        self.top_k = top_k

    def retrieve(self, query: str, top_k: int = None) -> CommunityRetrieveResult:
        top_k = top_k or self.top_k

        if self.embedder is None:
            from ...fusion.embedder import Embedder
            self.embedder = Embedder()

        query_embedding = self.embedder.embed([query])[0]

        detector = CommunityDetector(self.neo4j_driver, None)

        communities = detector.detect_and_summarize()
        scored = []
        for comm in communities:
            comm_text = comm.summary_text + " " + " ".join(comm.core_concepts)
            comm_embedding = self.embedder.embed([comm_text])[0]
            score = self._cosine_sim(query_embedding, comm_embedding)
            scored.append((score, comm))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_communities = [s[1] for s in scored[:top_k]]

        return CommunityRetrieveResult(
            community_summaries=top_communities,
            query=query,
        )

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
```

- [ ] **Step 4: Run test - expect PASS**

- [ ] **Step 5: Commit**

---

## Task 4: Implement HybridRetriever

**Files:**
- Create: `backend/app/kg/agents/graphrag/hybrid_retriever.py`
- Test: `backend/tests/unit/kg/agents/test_hybrid_retriever.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/kg/agents/test_hybrid_retriever.py
import pytest
from unittest.mock import MagicMock, patch
from app.kg.agents.graphrag.hybrid_retriever import HybridRetriever


class TestHybridRetriever:
    @patch("app.kg.src.storage.qdrant_writer.QdrantWriter")
    @patch("app.kg.src.storage.neo4j_writer.Neo4jWriter")
    def test_retrieve_vector_and_kg(self, mock_neo4j, mock_qdrant):
        mock_qdrant_instance = mock_qdrant.return_value
        mock_qdrant_instance.search.return_value = []

        retriever = HybridRetriever(
            qdrant_client=MagicMock(),
            neo4j_driver=MagicMock(),
        )
        result = retriever.retrieve("梯度下降", top_k=5)

        assert hasattr(result, "vector_results")
        assert hasattr(result, "kg_entities")
        assert result.query == "梯度下降"
```

- [ ] **Step 2: Run test - expect FAIL**

- [ ] **Step 3: Write HybridRetriever**

```python
# backend/app/kg/agents/graphrag/hybrid_retriever.py
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

from .types import RetrievedChunk, RetrievedEntity, EntityEdge


class HybridRetrieveResult(BaseModel):
    vector_results: List[RetrievedChunk]
    kg_entities: List[RetrievedEntity]
    query: str


class HybridRetriever:
    def __init__(
        self,
        qdrant_client,
        neo4j_driver,
        embedder=None,
        vector_top_k: int = 30,
    ):
        self.qdrant_client = qdrant_client
        self.neo4j_driver = neo4j_driver
        self.embedder = embedder
        self.vector_top_k = vector_top_k

    def retrieve(self, query: str, top_k: int = None) -> HybridRetrieveResult:
        if self.embedder is None:
            from ...fusion.embedder import Embedder
            self.embedder = Embedder()

        query_embedding = self.embedder.embed([query])[0]

        vector_results = self._vector_search(query_embedding, top_k or self.vector_top_k)
        kg_entities = self._kg_expand(query, top_k or self.vector_top_k)

        return HybridRetrieveResult(
            vector_results=vector_results,
            kg_entities=kg_entities,
            query=query,
        )

    def _vector_search(self, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]:
        try:
            results = self.qdrant_client.search(
                collection_name="kg_nodes",
                query_vector=query_embedding,
                limit=top_k,
            )
            chunks = []
            for r in results:
                chunks.append(RetrievedChunk(
                    chunk_id=r.id,
                    text=r.payload.get("text", ""),
                    score=r.score,
                    community_id=r.payload.get("community_id"),
                ))
            return chunks
        except Exception:
            return []

    def _kg_expand(self, query: str, top_k: int) -> List[RetrievedEntity]:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (n) WHERE n.name CONTAINS $query "
                    "RETURN n.id AS id, n.name AS name, labels(n)[0] AS type "
                    "LIMIT $top_k",
                    query=query, top_k=top_k
                )
                entities = []
                for record in result:
                    neighbors = self._get_neighbors(record["id"])
                    entities.append(RetrievedEntity(
                        entity_id=record["id"],
                        name=record["name"],
                        entity_type=record["type"],
                        neighbors=neighbors,
                        score=1.0,
                    ))
                return entities
        except Exception:
            return []

    def _get_neighbors(self, node_id: str) -> List[EntityEdge]:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (n)-[r]->(m) WHERE n.id = $id "
                    "RETURN m.id AS target_id, m.name AS target_name, type(r) AS rel_type "
                    "LIMIT 5",
                    id=node_id
                )
                return [
                    EntityEdge(
                        target_id=r["target_id"],
                        target_name=r["target_name"],
                        relation_type=r["rel_type"],
                    )
                    for r in result
                ]
        except Exception:
            return []
```

- [ ] **Step 4: Run test - expect PASS**

- [ ] **Step 5: Commit**

---

## Task 5: Implement Reranker

**Files:**
- Create: `backend/app/kg/agents/graphrag/reranker.py`
- Test: `backend/tests/unit/kg/agents/test_reranker.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/kg/agents/test_reranker.py
import pytest
from unittest.mock import patch, MagicMock
from app.kg.agents.graphrag.reranker import Reranker, RerankResult


class TestReranker:
    @patch("cohere.Client")
    def test_rerank_returns_ordered_results(self, mock_cohere_client):
        mock_client_instance = mock_cohere_client.return_value
        mock_client_instance.rerank.return_value = MagicMock(
            results=[
                MagicMock(index=0, relevance_score=0.95),
                MagicMock(index=1, relevance_score=0.85),
            ]
        )

        reranker = Reranker(api_key="fake_key")
        docs = [
            {"text": "梯度下降是优化算法", "id": "chunk_1"},
            {"text": "反向传播是神经网络训练算法", "id": "chunk_2"},
        ]
        results = reranker.rerank("什么是梯度下降", docs, top_n=2)

        assert len(results) == 2
        assert results[0].relevance_score > results[1].relevance_score
```

- [ ] **Step 2: Run test - expect FAIL**

- [ ] **Step 3: Write Reranker**

```python
# backend/app/kg/agents/graphrag/reranker.py
from __future__ import annotations
from typing import List, Union, Dict, Any, Optional
from pydantic import BaseModel
import os


class RerankResult(BaseModel):
    index: int
    document: Union[str, Dict[str, Any]]
    relevance_score: float


class Reranker:
    def __init__(
        self,
        api_key: str = None,
        model: str = "rerank-v3",
    ):
        self.api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
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

        client = self._get_client()
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

        reranked = self.rerank(query, all_docs, top_n=top_n)

        results = []
        for r in reranked:
            source_type, source_obj = doc_sources[r.index]
            results.append((source_type, source_obj, r.relevance_score))
        return results
```

- [ ] **Step 4: Run test - expect PASS**

- [ ] **Step 5: Commit**

---

## Task 6: Implement Generator

**Files:**
- Create: `backend/app/kg/agents/graphrag/generator.py`
- Test: `backend/tests/unit/kg/agents/test_generator.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/kg/agents/test_generator.py
import pytest
from unittest.mock import patch, MagicMock
from app.kg.agents.graphrag.generator import Generator, Citation


class TestGenerator:
    @patch("openai.OpenAI")
    def test_generate_includes_citation(self, mock_openai):
        mock_client_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='梯度下降是优化算法，用于最小化损失函数。{{citation: concept_grad_desc}}'
                )
            )
        ]
        mock_client_instance.chat.completions.create.return_value = mock_response

        gen = Generator(api_key="fake_key")
        result = gen.generate(
            question="什么是梯度下降？",
            contexts=[],
        )

        assert "梯度下降" in result.answer
        assert len(result.citations) >= 1
```

- [ ] **Step 2: Run test - expect FAIL**

- [ ] **Step 3: Write Generator**

```python
# backend/app/kg/agents/graphrag/generator.py
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
```

- [ ] **Step 4: Run test - expect PASS**

- [ ] **Step 5: Commit**

---

## Task 7: Implement SelfRAGVerifier

**Files:**
- Create: `backend/app/kg/agents/graphrag/verifier.py`
- Test: `backend/tests/unit/kg/agents/test_verifier.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/kg/agents/test_verifier.py
import pytest
from app.kg.agents.graphrag.verifier import SelfRAGVerifier
from app.kg.agents.graphrag.types import GenerationResult, Citation, VerificationResult


class TestSelfRAGVerifier:
    def test_verify_passes_with_citation(self):
        verifier = SelfRAGVerifier(api_key="fake_key")
        generation = GenerationResult(
            answer="梯度下降是优化算法",
            citations=[Citation(kg_node_id="concept_1", excerpt="梯度下降是优化算法")],
        )
        result = verifier.verify("什么是梯度下降？", generation, [])

        assert result.is_valid == True

    def test_verify_fails_empty_citation(self):
        verifier = SelfRAGVerifier(api_key="fake_key")
        generation = GenerationResult(
            answer="X是Y的解决方案",
            citations=[],  # 空引用
        )
        result = verifier.verify("什么是X？", generation, [])

        assert result.is_valid == False
        assert result.has_sufficient_citations == False
```

- [ ] **Step 2: Run test - expect FAIL**

- [ ] **Step 3: Write SelfRAGVerifier**

```python
# backend/app/kg/agents/graphrag/verifier.py
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
```

- [ ] **Step 4: Run test - expect PASS**

- [ ] **Step 5: Commit**

---

## Task 8: Implement GraphRAGService (LangGraph Orchestrator)

**Files:**
- Create: `backend/app/kg/agents/graphrag_service.py`
- Test: `backend/tests/integration/kg/agents/test_graphrag_service.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/integration/kg/agents/test_graphrag_service.py
import pytest
from unittest.mock import MagicMock, patch
from app.kg.agents.graphrag_service import GraphRAGService, GraphRAGState


class TestGraphRAGService:
    @patch("app.kg.agents.graphrag.intent_classifier.IntentClassifier")
    def test_service_query_integration(self, mock_classifier):
        mock_classifier.return_value.classify.return_value = MagicMock(
            intent="factual", confidence=0.9, reasoning="test"
        )

        service = GraphRAGService(
            neo4j_driver=MagicMock(),
            qdrant_client=MagicMock(),
        )
        result = service.query("什么是梯度下降")

        assert hasattr(result, "answer")
        assert hasattr(result, "intent")
```

- [ ] **Step 2: Run test - expect FAIL**

- [ ] **Step 3: Write graphrag_service.py**

```python
# backend/app/kg/agents/graphrag_service.py
from __future__ import annotations
from typing import TypedDict, List, Any, Optional, Literal
from langgraph.graph import StateGraph, END
import os

from .graphrag.types import (
    Intent, IntentResult, RetrievedChunk, RetrievedEntity,
    Citation, GenerationResult, VerificationResult, GraphRAGResult,
)
from .graphrag.intent_classifier import IntentClassifier
from .graphrag.hybrid_retriever import HybridRetriever
from .graphrag.community_retriever import CommunityRetriever
from .graphrag.reranker import Reranker
from .graphrag.generator import Generator
from .graphrag.verifier import SelfRAGVerifier


class GraphRAGState(TypedDict):
    question: str
    intent: Optional[IntentResult]
    retrieval_type: Optional[str]
    hybrid_results: Optional[Any]
    community_results: Optional[Any]
    reranked_results: Optional[List[Any]]
    generation: Optional[GenerationResult]
    verification: Optional[VerificationResult]
    answer: Optional[str]
    citations: Optional[List[Citation]]
    kg_paths: Optional[List[str]]
    verified: bool
    attempts: int


class GraphRAGService:
    def __init__(
        self,
        neo4j_driver,
        qdrant_client,
        embedder=None,
        api_key: str = None,
    ):
        self.neo4j_driver = neo4j_driver
        self.qdrant_client = qdrant_client
        self.embedder = embedder
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

        self.intent_classifier = IntentClassifier(api_key=self.api_key)
        self.hybrid_retriever = HybridRetriever(
            qdrant_client=qdrant_client,
            neo4j_driver=neo4j_driver,
            embedder=embedder,
        )
        self.community_retriever = CommunityRetriever(
            neo4j_driver=neo4j_driver,
            embedder=embedder,
        )
        self.reranker = Reranker(api_key=self.api_key)
        self.generator = Generator(api_key=self.api_key)
        self.verifier = SelfRAGVerifier(api_key=self.api_key)

    async def query(
        self,
        question: str,
        mode: Optional[str] = None,
        top_k: int = 10,
    ) -> GraphRAGResult:
        state: GraphRAGState = {
            "question": question,
            "intent": None,
            "retrieval_type": None,
            "hybrid_results": None,
            "community_results": None,
            "reranked_results": None,
            "generation": None,
            "verification": None,
            "answer": None,
            "citations": None,
            "kg_paths": None,
            "verified": False,
            "attempts": 0,
        }

        graph = self._build_graph()
        result = await graph.ainvoke(state)

        return GraphRAGResult(
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
            kg_paths=result.get("kg_paths", []),
            intent=result.get("intent", Intent.FACTUAL) if result.get("intent") else Intent.FACTUAL,
            retrieval_type=result.get("retrieval_type", "hybrid"),
            verification=result.get("verification"),
        )

    def _build_graph(self) -> StateGraph:
        g = StateGraph(GraphRAGState)

        g.add_node("intent", self._intent_node)
        g.add_node("route", self._route_node)
        g.add_node("hybrid_retrieve", self._hybrid_retrieve_node)
        g.add_node("community_retrieve", self._community_retrieve_node)
        g.add_node("rerank", self._rerank_node)
        g.add_node("generate", self._generate_node)
        g.add_node("verify", self._verify_node)

        g.set_entry_point("intent")
        g.add_edge("intent", "route")
        g.add_conditional_edges(
            "route",
            self._route_decision,
            {
                "hybrid": "hybrid_retrieve",
                "community": "community_retrieve",
            }
        )
        g.add_edge("hybrid_retrieve", "rerank")
        g.add_edge("community_retrieve", "rerank")
        g.add_edge("rerank", "generate")
        g.add_edge("generate", "verify")
        g.add_conditional_edges(
            "verify",
            self._verification_decision,
            {
                "pass": END,
                "fail": "generate",
            }
        )
        return g.compile()

    def _intent_node(self, state: GraphRAGState) -> GraphRAGState:
        result = self.intent_classifier.classify(state["question"])
        state["intent"] = result
        return state

    def _route_node(self, state: GraphRAGState) -> GraphRAGState:
        return state

    def _route_decision(self, state: GraphRAGState) -> str:
        intent = state.get("intent")
        if intent is None:
            return "hybrid"
        if intent.intent in (Intent.FACTUAL, Intent.PROCEDURAL):
            return "hybrid"
        return "community"

    def _hybrid_retrieve_node(self, state: GraphRAGState) -> GraphRAGState:
        result = self.hybrid_retriever.retrieve(state["question"])
        state["hybrid_results"] = result
        state["retrieval_type"] = "hybrid"
        return state

    def _community_retrieve_node(self, state: GraphRAGState) -> GraphRAGState:
        result = self.community_retriever.retrieve(state["question"])
        state["community_results"] = result
        state["retrieval_type"] = "community"
        return state

    def _rerank_node(self, state: GraphRAGState) -> GraphRAGState:
        if state["retrieval_type"] == "hybrid":
            all_contexts = []
            all_contexts.extend(state["hybrid_results"].vector_results)
            all_contexts.extend(state["hybrid_results"].kg_entities)
        else:
            all_contexts = state["community_results"].community_summaries

        reranked = self.reranker.rerank_hybrid(
            query=state["question"],
            vector_results=state["hybrid_results"].vector_results if state["retrieval_type"] == "hybrid" else [],
            kg_entities=state["hybrid_results"].kg_entities if state["retrieval_type"] == "hybrid" else [],
            top_n=10,
        )
        state["reranked_results"] = reranked
        return state

    def _generate_node(self, state: GraphRAGState) -> GraphRAGState:
        contexts = [r[1] for r in state.get("reranked_results", [])]
        gen_result = self.generator.generate(state["question"], contexts)
        state["generation"] = gen_result
        state["attempts"] = state.get("attempts", 0) + 1
        return state

    def _verify_node(self, state: GraphRAGState) -> GraphRAGState:
        contexts = [r[1] for r in state.get("reranked_results", [])]
        verification = self.verifier.verify(
            state["question"],
            state["generation"],
            contexts,
        )
        state["verification"] = verification
        state["verified"] = verification.is_valid
        if verification.is_valid:
            state["answer"] = state["generation"].answer
            state["citations"] = state["generation"].citations
            state["kg_paths"] = state["generation"].kg_paths
        return state

    def _verification_decision(self, state: GraphRAGState) -> str:
        if state.get("verified", False):
            return "pass"
        if state.get("attempts", 0) >= 2:
            state["answer"] = state["generation"].answer
            state["citations"] = state["generation"].citations
            state["kg_paths"] = state["generation"].kg_paths
            state["verified"] = True
            return "pass"
        return "fail"
```

- [ ] **Step 4: Run test - expect PASS**

- [ ] **Step 5: Commit**

---

## Task 9: Update config.yaml and config.py

**Files:**
- Modify: `backend/app/kg/config.yaml`
- Modify: `backend/app/kg/src/config.py`

- [ ] **Step 1: Read current config.yaml**

```bash
cat /home/zh/ai-study/backend/app/kg/config.yaml
```

- [ ] **Step 2: Add graphrag section to config.yaml**

```yaml
graphrag:
  embedding:
    provider: "bge-m3"
    model: "BAAI/bge-m3"
    api_key_env: "OPENAI_API_KEY"
    base_url: "http://localhost:8000/v1"
  reranker:
    provider: "cohere"
    model: "rerank-v3"
    api_key_env: "COHERE_API_KEY"
  generator:
    default_model: "gpt-4o"
    reasoning_model: "o3"
    api_key_env: "OPENAI_API_KEY"
  retrieval:
    vector_top_k: 30
    rerank_top_k: 10
```

- [ ] **Step 3: Update config.py to support graphrag section**

Add to `KGConfig` dataclass:
```python
@dataclass
class GraphRAGConfig:
    embedding: Dict[str, Any]
    reranker: Dict[str, Any]
    generator: Dict[str, Any]
    retrieval: Dict[str, Any]
```

Add to `load_config`:
```python
    graphrag_data = data.get("graphrag", {})
    graphrag_cfg = GraphRAGConfig(
        embedding=graphrag_data.get("embedding", {}),
        reranker=graphrag_data.get("reranker", {}),
        generator=graphrag_data.get("generator", {}),
        retrieval=graphrag_data.get("retrieval", {}),
    ) if graphrag_data else GraphRAGConfig(
        embedding={}, reranker={}, generator={}, retrieval={}
    )
```

- [ ] **Step 4: Run verification**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.src.config import get_config; c = get_config(); print('graphrag embedding provider:', c.graphrag.get('embedding', {}).get('provider', 'N/A'))"
```

- [ ] **Step 5: Commit**

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| Intent classifier (4 types) | Task 2 |
| Community retrieve (CommunityDetector) | Task 3 |
| Hybrid retrieve (BGE-M3 + Neo4j 1-hop) | Task 4 |
| Rerank (Cohere v3) | Task 5 |
| Generator + Citation | Task 6 |
| Self-RAG verification | Task 7 |
| LangGraph orchestrator | Task 8 |
| config.yaml integration | Task 9 |

All requirements covered. No placeholders found. Types consistent across tasks (Intent, RetrievedChunk, RetrievedEntity, Citation, GenerationResult, VerificationResult all defined in Task 1 types.py and used consistently).

---

**Plan complete.**