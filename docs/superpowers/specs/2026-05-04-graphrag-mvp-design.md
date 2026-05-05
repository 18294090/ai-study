# GraphRAG MVP Implementation Spec

> **Date:** 2026-05-04
> **Status:** Draft
> **Parent:** LearnHub v2.0 Design (2026-05-04-intelligent-learning-system-design.md)

## 1. Goal

实现 GraphRAG 统一检索层 MVP，作为所有下游任务（Tutor/题库/推荐）的统一入口。完整流程：意图分类 → 路由 → 混合召回 → Rerank → LLM生成+Citation锚定 → Self-RAG验证。

## 2. Architecture

```
User Question
      ↓
Intent Classifier (LLM, structured output)
      ↓
┌─────────────────────────────────────┐
│ Route Decision:                      │
│ factual/procedural → Hybrid Retrieve │
│ explanatory/meta → Community Retrieve│
└─────────────────────────────────────┘
        ↓                    ↓
  Hybrid Retrieve      Community Retrieve
  (BGE-M3 + Neo4j)     (CommunityDetector)
        ↓                    ↓
      Rerank (Cohere Rerank v3)
        ↓
  LLM Generate + Citation
        ↓
   Self-RAG Verify
        ↓
  Output: answer + citations[] + kg_paths[]
```

## 3. Components

### 3.1 Intent Classifier

**File:** `backend/app/kg/agents/graphrag/intent_classifier.py`

Intent types: `factual`, `procedural`, `explanatory`, `meta`

```python
class Intent(str, Enum):
    FACTUAL = "factual"        # 具体知识点查询
    PROCEDURAL = "procedural"  # 步骤/过程类问题
    EXPLANATORY = "explanatory" # 概念解释类
    META = "meta"              # 关于学习本身

class IntentResult(BaseModel):
    intent: Intent
    confidence: float
    reasoning: str
```

路由规则：
- `factual` → Hybrid Retrieve
- `procedural` → Hybrid Retrieve
- `explanatory` → Community Retrieve
- `meta` → Community Retrieve

### 3.2 Hybrid Retriever

**File:** `backend/app/kg/agents/graphrag/hybrid_retriever.py`

```python
class HybridRetrieveResult(BaseModel):
    vector_results: List[RetrievedChunk]  # BGE-M3 dense召回
    kg_entities: List[RetrievedEntity]    # Neo4j 1-hop扩展
    query: str

@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    community_id: Optional[str]
    textbook_anchor: Optional[TextbookAnchor]

@dataclass
class RetrievedEntity:
    entity_id: str
    name: str
    entity_type: EntityType
    neighbors: List[EntityEdge]  # 1-hop扩展
    score: float
```

流程：
1. BGE-M3 embedding → Qdrant vector search (top-30)
2. Neo4j entity match (基于 entity name) → 1-hop neighbors
3. 结果合并去重

### 3.3 Community Retriever

**File:** `backend/app/kg/agents/graphrag/community_retriever.py`

复用现有 `CommunityDetector`，增加摘要检索：

```python
class CommunityRetrieveResult(BaseModel):
    community_summaries: List[CommunitySummary]
    query: str
```

流程：
1. Query → BGE-M3 embedding → Qdrant community collection search
2. 返回 top-5 最相关社区摘要
3. 每个摘要附核心概念+关系列表

### 3.4 Reranker

**File:** `backend/app/kg/agents/graphrag/reranker.py`

使用 Cohere Rerank v3：

```python
class Reranker:
    def __init__(self, api_key: str, model: str = "rerank-v3"):
        self.client = cohere.Client(api_key)

    def rerank(
        self,
        query: str,
        documents: List[Union[str, dict]],
        top_n: int = 10,
    ) -> List[RerankResult]:
```

合并向量召回和KG扩展结果，统一 Rerank 输出 top-10。

### 3.5 Generator

**File:** `backend/app/kg/agents/graphrag/generator.py`

```python
class Citation(BaseModel):
    kg_node_id: str
    chapter_id: Optional[str]
    paragraph_offset: Optional[int]
    excerpt: str

class GenerationResult(BaseModel):
    answer: str
    citations: List[Citation]
    kg_paths: List[str]  # KG路径描述
    metadata: dict

class Generator:
    SYSTEM_PROMPT = """你是一个知识图谱问答助手。
    规则：
    - 必须引用相关KG节点，使用格式：{{citation: node_id}}
    - 仅基于提供的证据回答，禁止臆造
    - 回答需要可解释，附上KG路径"""

    def generate(
        self,
        question: str,
        contexts: List[RetrievedChunk | RetrievedEntity | CommunitySummary],
        model: str,
    ) -> GenerationResult:
```

### 3.6 Self-RAG Verifier

**File:** `backend/app/kg/agents/graphrag/verifier.py`

```python
class VerificationResult(BaseModel):
    is_valid: bool
    has_sufficient_citations: bool
    has_hallucination: bool
    is_within_scope: bool
    feedback: str
    issues: List[str]

class SelfRAGVerifier:
    def verify(
        self,
        question: str,
        generation: GenerationResult,
        retrieval_contexts: List[Any],
    ) -> VerificationResult:
```

验证规则：
1. **has_sufficient_citations**: 答案中每个声明都有 citation 支撑
2. **has_hallucination**: 引用的 KG 节点在上下文中真实存在
3. **is_within_scope**: 没有超出检索范围的推断

若验证失败，返回 `is_valid=False` + 具体问题列表。

### 3.7 GraphRAG Service (Orchestrator)

**File:** `backend/app/kg/agents/graphrag_service.py`

LangGraph 编排：

```python
class GraphRAGResult(BaseModel):
    answer: str
    citations: List[Citation]
    kg_paths: List[str]
    intent: Intent
    retrieval_type: str  # "hybrid" | "community"
    verification: VerificationResult

class GraphRAGService:
    async def query(
        self,
        question: str,
        mode: Optional[str] = None,  # None=auto, or force mode
        top_k: int = 10,
    ) -> GraphRAGResult:
```

LangGraph DAG:
```
intent_classify → route_decision
route_decision → hybrid_retrieve (if factual/procedural)
route_decision → community_retrieve (if explanatory/meta)
hybrid_retrieve → rerank
community_retrieve → rerank
rerank → generate
generate → verify
verify → (END or regenerate)
```

### 3.8 config.yaml Integration

Add to `backend/app/kg/config.yaml`:

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

## 4. File Structure

```
backend/app/kg/
├── agents/
│   ├── graphrag/
│   │   ├── __init__.py
│   │   ├── intent_classifier.py
│   │   ├── hybrid_retriever.py
│   │   ├── community_retriever.py
│   │   ├── reranker.py
│   │   ├── generator.py
│   │   ├── verifier.py
│   │   └── types.py           # Shared Pydantic types
│   └── graphrag_service.py    # LangGraph orchestrator
├── src/
│   ├── config.py              # Update to support graphrag section
│   └── ...
```

## 5. Dependencies

| Package | Purpose |
|---------|---------|
| `cohere` | Rerank v3 API |
| `sentence-transformers` | BGE-M3 local embedding |
| `vllm` | Local embedding serving (optional) |
| `langgraph` | DAG orchestration |

安装：`pip install cohere sentence-transformers langgraph`

## 6. Configuration

所有配置通过 `config.yaml` 管理，环境变量注入敏感信息：
- `OPENAI_API_KEY`: 生成模型 API key
- `COHERE_API_KEY`: Rerank API key
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Neo4j 连接
- `QDRANT_URL`: Qdrant 连接

## 7. Out of Scope (MVP)

- 多模态检索（图片/视频理解）
- 跨教材联合查询
- 增量索引更新
- 缓存层（Redis）
- 流量控制/熔断

## 8. Testing

| Test | Description |
|------|-------------|
| `test_intent_classifier` | 验证4类意图分类准确性 |
| `test_hybrid_retriever` | 向量+KG召回完整性 |
| `test_reranker` | Rerank前后排序质量 |
| `test_generator_citation` | Citation格式正确、节点ID有效 |
| `test_verifier_false_citation` | 验证能检测空引用/幻觉 |
| `test_full_pipeline` | 端到端集成测试 |

## 9. Implementation Order

1. `intent_classifier.py` - 意图分类（最快见效）
2. `types.py` - 共享类型定义
3. `community_retriever.py` - 复用 `CommunityDetector`
4. `hybrid_retriever.py` - BGE-M3 + Neo4j 1-hop
5. `reranker.py` - Cohere Rerank v3 集成
6. `generator.py` - LLM 生成 + Citation
7. `verifier.py` - Self-RAG 验证
8. `graphrag_service.py` - LangGraph DAG 编排
9. 更新 `config.yaml` + `config.py` 支持 graphrag section
10. 测试覆盖

## 10. Acceptance Criteria

- [ ] 意图分类：对factual/procedural/explanatory/meta四类问题分类正确率 ≥ 85%
- [ ] Citation锚定：100%答案包含有效citation，无空引用
- [ ] Self-RAG验证：能检测出无引用支撑的声明
- [ ] 端到端延迟：P95 < 5s（非推理模型）
- [ ] 路由正确性：factual/procedural→混合召回，explanatory/meta→社区召回
