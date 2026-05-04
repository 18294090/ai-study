# 教材知识图谱构建系统 - 实现计划 (v2.1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.
>
> **对齐 spec：** [2026-05-04-intelligent-learning-system-design.md](../specs/2026-05-04-intelligent-learning-system-design.md) v2.1
>
> **v2.1 增量：** Contextual Retrieval 预处理（F1 +35%）、Personalized PageRank 多跳推理、Node2Vec 链接预测、UniMERNet/Docling 解析器扩充、**摘要驱动快通道双路由**（借鉴 Graphusion 两阶段模式，降本 40-50%）、**Pedagogical KG 章节层级骨干**（textbook→chapter→section）。

## 架构原则：DAG 优先，非 Agent 中心

KG 抽取属于 spec §3.0/§6.9 中明确规定的"**应做成确定性 DAG 而非 Agent**"的场景。本计划据此：

- 主管线用 **LangGraph DAG + structured outputs**，不走 ReAct / 自由 agent。
- 文中"Domain Extractor / Pedagogical Tagger / Skill Mapper / Verifier" 等命名沿用了"Agent"语义，但**实现上是无状态的 LLM 调用节点**（单步、强 schema、可重放、可评测）。
- **DeerFlow 2.0 仅用于研究型旁路**（如教材外延知识补全、Expert Reviewer 协作），不进入本批处理管线。
- 所有节点必须满足：可重放幂等、cost cap、可评测、structured outputs。

## Goal

构建 GraphRAG 范式下的三层知识图谱抽取系统：Domain KG（学科）+ Pedagogical KG（教学）+ Cognitive Diagnostic KG（认知诊断），支持文理学科、PDF/扫描件输入、可计算公式、章节锚定、社区检测与跨教材融合。

**Architecture:**
```
教材 PDF
  ↓ MinerU 2.0 + Marker + Nougat + UniMERNet + Docling — 多解析器投票
章节结构化文档（含章节锚点）
  ↓ Lead Agent（LangGraph 编排）
  ↓ 语义分块（BGE-M3 滑动窗口边界检测，章/节优先，重叠 10-15%）
  ↓ 章节类型分类器（公式密度 + 标题语义 + 摘要长度）
       ├─ 快通道（文科论述/概念性章节，降本 40-50%）：
       │    章节摘要 → 推理模型直接抽取；无需 Contextual Retrieval（不入向量库）
       └─ 慢通道（STEM 推导密集章节、定理-证明-反例、边界条件 — 防长尾丢失）：
            原文全文分块 → Contextual Retrieval 预处理（每块前置 LLM 生成的位置说明，
            F1 +35%，仅慢通道 chunk 才执行，避免快通道浪费）
            → 长上下文抽取（Gemini 1M / Claude 200K + prompt caching）
  ↓
Sub-Agents 并行抽取（structured outputs，零解析失败）[★ 共享单例 BGE-M3 Embedder]
  ├─ Domain Extractor   (推理模型 o3 / R1)
  ├─ Pedagogical Tagger (textbook / chapter / section / lesson / objective / misconception)
  │     ↑ 章节层级骨干（textbook→chapter→section→objective）作为 Pedagogical KG 一等结构
  └─ Skill Mapper       (Q-matrix item→skill)
  ↓
融合层：[★ 复用共享 BGE-M3 Embedder，不重新加载模型]
  ├─ BGE-M3 embedding + 类型约束 + LLM verifier 三阶段消歧
  ├─ 跨教材冲突检测 → Expert Reviewer 仲裁队列（Postgres arbitration_queue 表，Task 14）
  ├─ Leiden 社区检测 + 层次化社区摘要（GraphRAG）
  └─ Node2Vec 链接预测 → 隐性 prerequisite_of → 人工仲裁队列（Task 14）
  ↓
评测 harness：F1 ≥ 门槛准入（★ 样本 < 200 时 CI 为 warning 模式，不 block PR — Task 10）
  ↓ [eval_passed == True]
存储：
  ├─ Neo4j（三层 schema，章节锚点，社区 ID）
  ├─ Qdrant（慢通道 chunk + 社区摘要 embedding；★ PPR 为查询时操作，不在构建时执行）
  └─ Postgres（评测集、版本表、审核队列 — Task 14）
  ↓
JY/T 合规导出（Task 13，条件执行）
```

**Tech Stack:** LangGraph, DSPy MIPROv2, Neo4j 5 (GDS — Leiden / Node2Vec / Personalized PageRank), Qdrant, BGE-M3, Cohere Rerank v3, OpenAI o3 / DeepSeek-R1 / Claude 4 / Claude Haiku 3.5 (Contextual Retrieval), OpenAI structured outputs / Outlines, Pydantic v2, SymPy, MinerU 2.0 / Marker / Nougat / UniMERNet / Docling, Ragas, Promptfoo, DVC, **rdflib 7 + pyshacl**（JY/T 标准合规序列化 + SHACL 验证）。

---

## 文件结构

```
kg/
├── skills/public/knowledge-extraction/SKILL.md
├── agents/
│   ├── lead_agent.py                  # LangGraph 编排
│   ├── domain_extractor.py            # Layer 1 抽取
│   ├── pedagogical_tagger.py          # Layer 2 抽取
│   ├── skill_mapper.py                # Layer 3 Q-matrix
│   ├── fusion_agent.py                # 消歧融合
│   ├── community_detector.py          # Leiden + 社区摘要
│   └── verifier_agent.py              # Self-RAG 校验
├── src/
│   ├── models/                        # Pydantic v2 模型 (三层 schema)
│   ├── parsers/                       # MinerU/Marker/Nougat 投票
│   ├── extractors/                    # structured outputs LLM 抽取
│   ├── fusion/                        # BGE-M3 + verifier 三阶段
│   ├── storage/                       # Neo4j + Qdrant 双写
│   ├── routing/                       # LLM 模型路由 + prompt caching
│   ├── eval/                          # 评测 harness
│   ├── formula/                       # LaTeX → SymPy AST
│   └── compliance/                    # ★ JY/T 标准合规模块（Task 13）
│       ├── ontology_mapper.py         #   内部 schema → JY/T 本体映射
│       ├── relation_mapper.py         #   内部关系 → JY/T 关系映射
│       ├── rdf_exporter.py            #   rdflib 序列化 → .ttl/.rdf
│       ├── validator.py               #   §8 证实方法实现
│       ├── jyt_0644_codes.py          #   JY/T 0644 学科/学段代码表
│       ├── shacl_shapes.ttl           #   SHACL 约束（必填字段 + 类型）
│       └── jyt_ontology.ttl           #   JY/T 本体声明（八个顶层类 + 标准关系，Task 13.8 Step 1 生成）
├── config/knowledge-graph.yaml
├── eval/
│   ├── kg_extraction_500.jsonl        # 评测集（DVC 管理）
│   └── baselines/
├── tests/
└── docs/schema.md                     # 三层 schema 文档
```

---

## 任务列表

### Task 1: 项目初始化与三层 Schema 定义

**Files:**
- Create: `kg/docs/schema.md`
- Create: `kg/config/knowledge-graph.yaml`
- Create: `kg/skills/public/knowledge-extraction/SKILL.md`

- [ ] **Step 1: 创建项目骨架**

```bash
mkdir -p kg/{skills/public/knowledge-extraction,agents,src/{models,parsers,extractors,fusion,storage,routing,eval,formula,compliance},config,eval/baselines,tests,docs}
```

- [ ] **Step 2: 三层 Schema 文档** — 创建 `kg/docs/schema.md`

```markdown
# 三层知识图谱 Schema

## Layer 1 — Domain KG（学科知识图谱）
实体类型：concept / formula / theorem / person / event / location / work / time / dataset
关系类型：is_a / part_of / causes / equivalent_to / generalizes / contradicts /
        applies_to / requires / before / after / similar_to / defined_by / example_of
属性：name, description, latex, sympy_ast, source_doc, confidence,
     textbook_anchor: {textbook_id, chapter_id, paragraph_offset},
     community_id (Leiden)
SKOS 标注（v2.1 新增）：
  skos:broader / skos:narrower  → 替代 is_a，获得传递性公理
  skos:related                  → 替代 similar_to，获得对称性约束
  skos:exactMatch               → Wikidata QID 强等价对齐
  skos:closeMatch               → 跨教材近似等价（不触发自动合并）
附加属性：skos_exact_match (wikidata_qid), skos_close_match, skos_broader, skos_related

## Layer 2 — Pedagogical KG（教学知识图谱）
实体：textbook / chapter / section / learning_objective / lesson / activity / assessment / misconception
       curriculum_standard_node（v2.1 新增）
       ★ textbook→chapter→section 章节层级骨干（借鉴两阶段模式），为学习路径规划提供章节粒度拓扑序
       ★ curriculum_standard_node：国家课标形式化节点，只读，一次性导入
         属性：standard_id / subject / grade_band / bloom_required / exam_scope / exam_weight
关系：textbook --contains--> chapter --contains--> section --contains--> learning_objective /
     concept --aligned_to--> curriculum_standard_node  # 强制字段，每个 concept 必须对齐
     concept --exam_scope--> {gaokao / zhongkao / 双减_excluded}
     teaches / prerequisite_of / assesses / addresses_misconception /
     estimated_minutes / bloom_level / dok_level

## Layer 3 — Cognitive Diagnostic KG
实体：skill / sub_skill / q_matrix_entry
关系：requires_skill / composed_of / mastery_threshold
用途：BKT/DKT 输入；IRT Q-matrix
```

- [ ] **Step 3: 配置文件** — `config/knowledge-graph.yaml`

```yaml
extraction:
  parsing:
    parsers: [mineru-2.0, marker, nougat, unimernet, docling]
    voting_strategy: confidence_weighted
    low_confidence_threshold: 0.7  # 低于此值进入人工抽检
  chunking:
    strategy: semantic              # BGE-M3 滑动窗口边界检测
    prefer_chapter_boundaries: true
    overlap_ratio: 0.12
    max_tokens: 8000
  contextual_retrieval:
    enabled: true                   # Anthropic Contextual Retrieval
    context_model: claude-haiku-3.5 # 廉价模型生成 chunk 上下文
    context_max_tokens: 100
    use_prompt_caching: true        # 全书一次缓存，每 chunk 复用
  chapter_routing:                  # 摘要驱动快通道 vs 全文慢通道
    enabled: true
    classifier_model: claude-haiku-3.5
    fast_path_signals:              # 满足任一即可入快通道
      - chapter_type: [overview, narrative, conceptual]
      - formula_density_below: 0.05
    slow_path_force:                # 满足任一强制走慢通道（防长尾丢失）
      - contains_proof: true
      - contains_theorem_with_conditions: true
      - contains_counter_example: true
      - subject: [math, physics, chemistry]
        and_chapter_type: derivation
    confidence_threshold: 0.75      # 分类置信度低于此值退化到慢通道
  domain:
    primary_model: o3              # 推理模型抽取主路径
    verifier_model: claude-3.7-thinking
    fallback_model: gpt-4o
    long_context_model: gemini-2.5-pro  # 全书长上下文
    use_prompt_caching: true
    structured_output: true        # 强制 schema-guided decoding
    max_chunk_tokens: 200000
  pedagogical:
    primary_model: claude-3.7
  skill_mapping:
    primary_model: o3
fusion:
  embedding_model: bge-m3
  similarity_threshold: 0.85
  type_constraint: true            # 必须同类型才合并
  llm_verifier_model: gpt-4o
  rerank_model: cohere-rerank-v3
graph_rag:
  community_detection: leiden
  resolution: 1.0
  summary_levels: [0, 1, 2]
  summary_model: gpt-4o
  personalized_pagerank:
    enabled: true                   # HippoRAG 2 风格多跳推理
    damping_factor: 0.85
    max_iterations: 20
    top_n: 30                       # PPR 输出 top-N 节点
link_prediction:
  enabled: true
  algorithm: node2vec               # Neo4j GDS
  walk_length: 80
  walks_per_node: 10
  embedding_dim: 128
  prediction_threshold: 0.75        # 高于此值进入人工仲裁队列
  target_relations: [prerequisite_of, requires]
curriculum_alignment:               # 课程标准锚点（v2.1 新增）
  enabled: true
  standard_source: official_pdf     # 从官方课标 PDF 一次性抽取
  standard_model: claude-3.7        # 抽取课标节点用
  standard_id_pattern: "GB-{year}-{subject}-{grade}-{chapter}-{section}"
  alignment_model: bge-m3           # 概念 ↔ 课标节点 embedding 匹配
  alignment_threshold: 0.80         # 低于此值不自动对齐，推入人工仲裁
  double_jian_filter: true          # exam_scope=双减_excluded 自动拦截 K12 推送
  wikidata_sync:                    # SKOS exactMatch → Wikidata QID 扩充
    enabled: true
    sync_model: gpt-4o-mini         # 廉价模型做 Wikidata SPARQL 补全
    fields: [definition, image_url, aliases_zh, related_topics]
storage:
  neo4j:
    uri: ${NEO4J_URI}
    database: knowledge_graph
  qdrant:
    url: ${QDRANT_URL}
    collection_nodes: kg_nodes
    collection_summaries: kg_communities
    collection_chunks: kg_chunks    # 含 contextual prefix 的 chunk 向量
eval:
  dataset_path: eval/kg_extraction_500.jsonl
  thresholds:
    precision: 0.80
    recall: 0.80
    f1: 0.80
budget:
  max_tokens_per_textbook: 5_000_000
  max_cost_usd_per_textbook: 50
```

- [ ] **Step 4: SKILL.md** — 简明版

```markdown
# Knowledge Extraction Skill (v2.1)

## Purpose
构建 GraphRAG 范式下的三层知识图谱（含 Contextual Retrieval + PPR 多跳推理）

## Pipeline
1. 多解析器投票文档解析（MinerU 2.0 / Marker / Nougat / UniMERNet / Docling）
2. 语义分块（BGE-M3 边界检测，章/节优先，重叠 10-15%）
3. **章节路由器**：快通道（文科/概念性章节，章节摘要直接抽取，降本 40-50%）vs 慢通道（STEM/定理/反例，全文分块 + **Contextual Retrieval 预处理**，F1 +35%）；★ Contextual Retrieval 仅慢通道执行，避免快通道浪费
4. 长上下文 + 结构化输出 LLM 抽取（Domain / Pedagogical 含章节层级骨干 / Skill）
5. BGE-M3 + 类型约束 + LLM verifier 三阶段消歧（★ BGE-M3 与步骤 2 共用单例）
6. Leiden 社区检测 + 层次摘要
7. **Node2Vec 链接预测** → 隐性 prerequisite_of → 人工仲裁队列（Task 14）
8. Neo4j + Qdrant 双写；★ PPR（Personalized PageRank）是查询时操作，不在构建管线中执行
9. JY/T 标准合规导出（Task 13，条件执行）
10. CI 评测准入（样本 ≥ 200 时 F1 ≥ 0.80 block；< 200 时为 warning 模式）

## Usage
/extract-knowledge --input book.pdf --subject math --output ./out
```

- [ ] **Step 5: 提交**

```bash
cd kg && git init && git add . && git commit -m "feat: v2.1 项目骨架（含 Contextual Retrieval + PPR + 链接预测）"
```

---

### Task 2: 核心数据模型（三层 + 章节锚定 + 公式）

**Files:**
- Create: `src/models/entities.py`
- Create: `src/models/triples.py`
- Create: `src/models/textbook.py`
- Create: `src/models/pedagogical.py`
- Create: `src/models/diagnostic.py`
- ★ `src/fusion/embedder.py` 在 **Task 6** 中创建，此处仅标注共享规则（P2-1）
- Create: `tests/test_models.py`

> ⚠️ **P2-2 Entity 继承关系说明**：`Entity`（Domain 层）/ `LearningObjective`、`Misconception`、`CurriculumStandardNode`（Pedagogical 层）/ `Skill`、`QMatrixEntry`（Diagnostic 层）均继承 `EntityBase`（含 `id`/`name`/`anchor`/`confidence`/`layer` 公共字段）。`Entity` 在基类之上增加 `latex/sympy_ast/community_id/skos_*/curriculum_anchor/jyt` 字段；教学层和诊断层实体**不包含**这些 Domain 专属字段。DAG 各节点的输入输出类型须声明为对应子类，不使用基类 `EntityBase` 作为泛型。

- [ ] **Step 1: Domain 实体与三元组** — `src/models/entities.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from enum import Enum

class EntityType(str, Enum):
    CONCEPT = "concept"; FORMULA = "formula"; THEOREM = "theorem"
    PERSON = "person"; EVENT = "event"; LOCATION = "location"
    WORK = "work"; TIME = "time"; DATASET = "dataset"

class RelationType(str, Enum):
    IS_A = "is_a"; PART_OF = "part_of"; CAUSES = "causes"
    EQUIVALENT_TO = "equivalent_to"; GENERALIZES = "generalizes"
    CONTRADICTS = "contradicts"; APPLIES_TO = "applies_to"
    REQUIRES = "requires"; BEFORE = "before"; AFTER = "after"
    SIMILAR_TO = "similar_to"; DEFINED_BY = "defined_by"
    EXAMPLE_OF = "example_of"

class TextbookAnchor(BaseModel):
    textbook_id: str
    chapter_id: str
    paragraph_offset: int = 0
    page: Optional[int] = None

class EntityBase(BaseModel):
    """所有层实体的公共基类（P2-2）"""
    id: str
    name: str
    anchor: Optional[TextbookAnchor] = None
    confidence: float = Field(1.0, ge=0, le=1)
    layer: Literal["domain", "pedagogical", "diagnostic"] = "domain"

class Entity(EntityBase):
    """Domain KG 实体，含 SKOS 语义标注和课标锚点（v2.1）"""
    layer: Literal["domain", "pedagogical", "diagnostic"] = "domain"
    type: EntityType
    description: Optional[str] = None
    latex: Optional[str] = None              # 公式 LaTeX
    sympy_ast: Optional[str] = None          # 可计算 AST（序列化）
    community_id: Optional[str] = None       # Leiden 社区 ID
    # SKOS 语义标注（v2.1，W3C 标准，获得传递性/对称性公理）
    skos_broader: Optional[str] = None       # 父概念 id（传递性公理）
    skos_related: List[str] = []             # 关联概念 ids（对称性约束）
    skos_exact_match: Optional[str] = None   # Wikidata QID（强等价）
    skos_close_match: Optional[str] = None   # 跨教材近似等价（不触发自动合并）
    # 课程标准锚点（v2.1，强制字段）
    curriculum_anchor: Optional[str] = None  # aligned_to curriculum_standard_node.id
    exam_scope: List[str] = []               # [gaokao / zhongkao / 双减_excluded ...]
    jyt: Optional["JYTCompliantFields"] = None  # 合规导出字段，懒填充（Task 13）
```

- [ ] **Step 2: 三元组** — `src/models/triples.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from .entities import Entity, RelationType, TextbookAnchor

class KnowledgeTriple(BaseModel):
    subject: Entity
    predicate: RelationType
    object: Entity
    confidence: float = Field(1.0, ge=0, le=1)
    anchor: Optional[TextbookAnchor] = None
    extracted_by: Optional[str] = None       # 模型名（溯源）
    verified_by: Optional[str] = None        # verifier 模型名

    def dedup_key(self) -> tuple:
        return (self.subject.name, self.subject.type, self.predicate, self.object.name, self.object.type)
```

- [ ] **Step 3: 教学层模型** — `src/models/pedagogical.py`

```python
from pydantic import BaseModel
from typing import List, Optional, Literal
from enum import Enum
from src.models.entities import EntityBase

class BloomLevel(str, Enum):
    REMEMBER = "remember"; UNDERSTAND = "understand"; APPLY = "apply"
    ANALYZE = "analyze"; EVALUATE = "evaluate"; CREATE = "create"

class LearningObjective(EntityBase):
    layer: Literal["domain", "pedagogical", "diagnostic"] = "pedagogical"
    description: str
    target_concepts: List[str]              # concept ids
    bloom_level: BloomLevel
    dok_level: int                          # 1-4
    estimated_minutes: int

class Misconception(EntityBase):
    layer: Literal["domain", "pedagogical", "diagnostic"] = "pedagogical"
    description: str
    related_concepts: List[str]
    example_wrong_answers: List[str] = []

class CurriculumStandardNode(EntityBase):
    """国家课程标准形式化节点（v2.1，只读，一次性从官方 PDF 导入）"""
    layer: Literal["domain", "pedagogical", "diagnostic"] = "pedagogical"
    standard_id: str                        # GB-2022-Math-7-3-2
    subject: str                            # math / physics / ...
    grade_band: str                         # 义教1-9 / 高中10-12
    content_requirement: str               # 原文摘录
    bloom_required: BloomLevel
    exam_scope: List[str]                   # [gaokao / zhongkao / 双减_excluded]
    exam_weight: Optional[float] = None    # 高考历年该知识点占分比例估算
    wikidata_qid: Optional[str] = None
```

- [ ] **Step 4: 诊断层 Q-matrix** — `src/models/diagnostic.py`

```python
from pydantic import BaseModel
from typing import List, Optional, Literal
from src.models.entities import EntityBase

class Skill(EntityBase):
    layer: Literal["domain", "pedagogical", "diagnostic"] = "diagnostic"
    parent_skill: Optional[str] = None
    mastery_threshold: float = 0.8

class QMatrixEntry(BaseModel):
    item_id: str                            # 题目 ID
    required_skills: List[str]              # skill ids
    weights: List[float]                    # 同长度，权重和=1
```

- [ ] **Step 5: 教材模型** — `src/models/textbook.py`

```python
from pydantic import BaseModel
from typing import List, Optional

class Section(BaseModel):
    """章节层级骨干：section 粒度（chapter 的子节点）"""
    section_id: str
    title: str
    parent_chapter_id: str
    content: str
    word_count: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None

class Chapter(BaseModel):
    chapter_id: str
    title: str
    level: int = 1
    parent_id: Optional[str] = None
    sections: List[Section] = []            # textbook→chapter→section 骨干
    content: str                            # 章节全文（sections 合并前缓存）
    word_count: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None

class Textbook(BaseModel):
    textbook_id: str
    title: str
    subject: str                            # math / physics / history / ...
    chapters: List[Chapter]
    total_words: int
    edition: Optional[str] = None
```

- [ ] **Step 6: 测试** — `tests/test_models.py`（覆盖三层、anchor、dedup_key、公式字段）

- [ ] **Step 7: 提交**

```bash
git add src/models tests/test_models.py && git commit -m "feat: 三层 schema 数据模型"
```

---

### Task 3: 多解析器文档解析（MinerU + Marker + Nougat 投票）

**Files:**
- Create: `src/parsers/multi_parser.py`
- Create: `src/formula/latex_to_sympy.py`
- Create: `tests/test_parsers.py`

- [ ] **Step 1: 解析器接口与投票**

```python
# src/parsers/multi_parser.py
from typing import Protocol, List
from src.models.textbook import Textbook, Chapter

class TextbookParser(Protocol):
    name: str
    def parse(self, pdf_path: str) -> Textbook: ...

class MultiParserVote:
    """五引擎并行解析（MinerU / Marker / Nougat / UniMERNet / Docling）；
    章节切分用多数投票，公式区域优先 Nougat + UniMERNet。"""
    def __init__(self, parsers: List[TextbookParser]):
        self.parsers = parsers

    def parse(self, pdf_path: str) -> Textbook:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.parsers)) as ex:
            results = list(ex.map(lambda p: p.parse(pdf_path), self.parsers))
        return self._vote(results)

    def _vote(self, results: List[Textbook]) -> Textbook:
        # 章节边界投票：以 page_start/title 哈希做多数表决
        # 公式：Nougat 结果覆盖其他
        ...
```

- [ ] **Step 2: 公式解析 LaTeX → SymPy AST** — `src/formula/latex_to_sympy.py`

```python
from sympy.parsing.latex import parse_latex
import sympy as sp

def latex_to_ast(latex: str) -> str | None:
    try:
        expr = parse_latex(latex)
        return sp.srepr(expr)
    except Exception:
        return None
```

- [ ] **Step 3: 测试 + 提交**

```bash
pytest tests/test_parsers.py -v
git add src/parsers src/formula tests/test_parsers.py
git commit -m "feat: 多解析器投票 + LaTeX/SymPy"
```

---

### Task 4: LLM 模型路由 + Prompt Caching + Structured Outputs

**Files:**
- Create: `src/routing/model_router.py`
- Create: `src/routing/structured_client.py`

- [ ] **Step 1: 路由器** — 简单意图路由 (`hard_extraction` / `general` / `cheap`)

```python
# src/routing/model_router.py
from typing import Literal, Type
from pydantic import BaseModel

ModelTier = Literal["reasoning", "general", "small", "long_ctx"]

class ModelRouter:
    def __init__(self, config: dict):
        self.config = config

    def select(self, task: str) -> ModelTier:
        return {
            "domain_extract": "long_ctx",
            "verify": "reasoning",
            "pedagogical_tag": "general",
            "skill_map": "reasoning",
            "summary": "general",
            "embedding": "small",
        }.get(task, "general")
```

- [ ] **Step 2: 结构化输出客户端**（强制 Pydantic schema，零解析失败）

```python
# src/routing/structured_client.py
from openai import OpenAI
from anthropic import Anthropic
from pydantic import BaseModel
from typing import Type, TypeVar

T = TypeVar("T", bound=BaseModel)

class StructuredClient:
    """OpenAI 结构化输出客户端。
    - OpenAI 的 prompt caching 无需显式标注，相同前缀内容自动命中缓存。
    - 若需使用 Anthropic Claude（支持 cache_control 显式标注），
      切换到 AnthropicStructuredClient（同模块内，仅为 Haiku 等 Anthropic 模型使用）。
    """
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    def extract(self, system: str, user: str, schema: Type[T],
                cached_prefix: str | None = None) -> T:
        messages = []
        if cached_prefix:
            # OpenAI 缓存靠前缀内容重复，无需额外字段。
            # 将全书目录 + few-shot 作为第一个 system 消息前缀以触发自动缓存。
            messages.append({"role": "system", "content": cached_prefix})
        messages += [{"role": "system", "content": system},
                     {"role": "user", "content": user}]
        resp = self.client.beta.chat.completions.parse(
            model=self.model, messages=messages, response_format=schema)
        return resp.choices[0].message.parsed
```

- [ ] **Step 3: 提交**

```bash
git add src/routing && git commit -m "feat: 模型路由 + 结构化输出客户端"
```

---

### Task 5: 三类抽取 Agent（Domain / Pedagogical / Skill）

**Files:**
- Create: `agents/domain_extractor.py`
- Create: `agents/pedagogical_tagger.py`
- Create: `agents/skill_mapper.py`
- Create: `tests/test_extractors.py`

- [ ] **Step 1: Domain 抽取 schema 与 prompt**

```python
# agents/domain_extractor.py
from pydantic import BaseModel
from typing import List
from src.models.entities import EntityType, RelationType
from src.models.textbook import Chapter
from src.routing.structured_client import StructuredClient

class _Ent(BaseModel):
    name: str; type: EntityType; description: str | None = None
    latex: str | None = None

class _Tri(BaseModel):
    subject: _Ent; predicate: RelationType; object: _Ent
    confidence: float = Field(0.8, ge=0.0, le=1.0)

class DomainExtraction(BaseModel):
    triples: List[_Tri]

DOMAIN_SYSTEM = """你是一个学科知识抽取专家。从教材文本中抽取知识三元组。
要求：
- 仅抽取教材直接断言的知识，置信度 ≥ 0.8 才输出
- 公式必须保留 LaTeX 原文
- 因果与归类关系优先
- 严禁臆造原文未提及的事实"""

class DomainExtractor:
    def __init__(self, client: StructuredClient):
        self.client = client

    def extract(self, chapter: Chapter, book_context: str) -> DomainExtraction:
        return self.client.extract(
            system=DOMAIN_SYSTEM,
            user=f"<chapter id={chapter.chapter_id} title='{chapter.title}'>\n{chapter.content}\n</chapter>",
            schema=DomainExtraction,
            cached_prefix=book_context,    # 全书目录 + few-shot 走 cache
        )
```

- [ ] **Step 2: Pedagogical 标注**（识别 learning_objective / misconception / bloom_level / dok_level）

```python
# agents/pedagogical_tagger.py — 类似结构，输出 Pedagogical schema
```

- [ ] **Step 3: Skill mapper（生成 Q-matrix 草稿）**

```python
# agents/skill_mapper.py — 输入 concept 列表 + 题目，输出 QMatrixEntry
```

- [ ] **Step 4: 测试**（mock LLM 返回，验证 structured 解析、置信度过滤）+ 提交

---

### Task 6: 融合层（BGE-M3 + 类型约束 + LLM verifier 三阶段消歧）

**Files:**
- Create: `src/fusion/embedder.py`
- Create: `src/fusion/entity_resolver.py`
- Create: `agents/verifier_agent.py`
- Create: `tests/test_fusion.py`

- [ ] **Step 1: BGE-M3 embedding 服务**（HTTP 或本地 FlagEmbedding）

```python
# src/fusion/embedder.py
from FlagEmbedding import BGEM3FlagModel
import numpy as np

class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model = BGEM3FlagModel(model_name, use_fp16=True)
    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, batch_size=64)['dense_vecs']
```

- [ ] **Step 2: 三阶段消歧器**

```python
# src/fusion/entity_resolver.py
from typing import List, Dict, Tuple
import numpy as np
from src.models.entities import Entity
from src.fusion.embedder import Embedder

class EntityResolver:
    def __init__(self, embedder: Embedder, verifier_fn,
                 sim_threshold: float = 0.85, ambiguous_band: tuple = (0.75, 0.85)):
        self.embedder = embedder
        self.verifier_fn = verifier_fn        # callable: (e1, e2) -> bool
        self.sim_threshold = sim_threshold
        self.ambiguous_band = ambiguous_band

    def cluster(self, entities: List[Entity]) -> Dict[str, List[Entity]]:
        # 1) 类型分桶（不同 type 不合并）
        # 2) 桶内 BGE-M3 相似度
        # 3) > sim_threshold 直接合并
        # 4) ambiguous_band 内调用 LLM verifier
        # 5) 否则不合并
        ...
```

- [ ] **Step 3: LLM verifier agent**（"以下两个实体是否指同一概念？"，结构化布尔输出 + 理由）

- [ ] **Step 4: 测试覆盖三阶段路径 + 提交**

---

### Task 7: Leiden 社区检测 + 层次化社区摘要（GraphRAG 核心）

**Files:**
- Create: `agents/community_detector.py`
- Create: `tests/test_community.py`

- [ ] **Step 1: 调用 Neo4j GDS Leiden**

```python
# agents/community_detector.py
class CommunityDetector:
    def __init__(self, neo4j_driver, summary_client: StructuredClient):
        self.driver = neo4j_driver
        self.summary_client = summary_client

    def detect(self, database: str = "neo4j") -> dict:
        with self.driver.session(database=database) as s:
            s.run("CALL gds.graph.project('kg', '*', '*')")
            s.run("""CALL gds.leiden.write('kg',
                {writeProperty: 'community_id', includeIntermediateCommunities: true})""")
            # 注意：Cypher 在有聚合函数时自动分组，无需 GROUP BY
            return s.run("MATCH (n) WHERE n.community_id IS NOT NULL "
                         "RETURN n.community_id AS c, count(*) AS size "
                         "ORDER BY size DESC").data()

    def summarize(self, community_id: str, level: int) -> str:
        # 拉取社区内节点 + 三元组 → 推理模型生成层次摘要
        # 摘要存入 Neo4j Community 节点 + Qdrant（用于全局型问答检索）
        ...
```

- [ ] **Step 2: 摘要 schema 与 prompt**（输出包含：核心概念、关键关系、典型应用、层级编号）

- [ ] **Step 3: 测试 + 提交**

---

### Task 8: Neo4j + Qdrant 双写存储

**Files:**
- Create: `src/storage/neo4j_writer.py`
- Create: `src/storage/qdrant_writer.py`
- Create: `src/storage/dual_writer.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Neo4j writer**（按 layer 创建标签 + 章节锚定为属性 + 约束）

```python
# 关键差异（vs v1）：
#   - 节点 label 包含 layer：(:concept:domain {...})
#   - 三元组关系属性带 anchor、extracted_by、verified_by
#   - 启动时 CREATE CONSTRAINT FOR (n:concept) REQUIRE n.id IS UNIQUE
#   - 写入用 UNWIND 批量化
```

- [ ] **Step 2: Qdrant writer**（节点 + 社区摘要双 collection）

```python
# kg_nodes:        node_id, layer, type, vec(BGE-M3 dense), payload(name, anchor)
# kg_communities:  community_id, level, vec, payload(summary)
```

- [ ] **Step 3: 双写一致性**（先 Neo4j，再 Qdrant；失败回滚 + 死信队列）

- [ ] **Step 4: 测试（mock 驱动）+ 提交**

---

### Task 9: LangGraph 编排 Lead Agent

**Files:**
- Create: `agents/lead_agent.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: LangGraph 状态机**

```python
# agents/lead_agent.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PipelineState(TypedDict):
    textbook_id: str
    chapters: list
    domain_triples: list
    pedagogical: list
    skills: list
    resolved_entities: list
    communities: list
    eval_passed: bool
    eval_report: dict                # eval_gate 结果（含 F1/P/R 及失败原因），供下游日志使用

def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("parse", parse_node)
    g.add_node("extract_domain", extract_domain_node)        # 并行分支
    g.add_node("tag_pedagogical", tag_pedagogical_node)      # 并行分支
    g.add_node("map_skills", map_skills_node)                # 并行分支
    # ★ fan-in：LangGraph 原生支持多条 add_edge 指向同一后继节点，
    #   框架会等待所有上游并行分支完成后再触发 fuse。
    #   不需要手动计数器（手动计数器无法可靠工作）。
    g.add_node("fuse", fuse_node)
    g.add_node("verify", verify_node)
    g.add_node("detect_communities", community_node)
    g.add_node("eval_gate", eval_gate_node)                  # F1 ≥ 门槛才放行
    g.add_node("eval_fail_report", eval_fail_report_node)    # 评测失败时输出诊断报告
    g.add_node("store", store_node)
    g.add_node("compliance_export", compliance_export_node)  # Task 13 合规导出

    g.set_entry_point("parse")
    # parse → 三路并行（LangGraph 支持一个节点 add_edge 到多个后继）
    g.add_edge("parse", "extract_domain")
    g.add_edge("parse", "tag_pedagogical")
    g.add_edge("parse", "map_skills")
    # 三路并行 → fan-in（直接连接到 fuse，LangGraph 原生等待所有分支完成）
    g.add_edge("extract_domain", "fuse")
    g.add_edge("tag_pedagogical", "fuse")
    g.add_edge("map_skills", "fuse")
    g.add_edge("fuse", "verify")
    g.add_edge("verify", "detect_communities")
    g.add_edge("detect_communities", "eval_gate")
    g.add_conditional_edges("eval_gate",
        lambda s: "store" if s["eval_passed"] else "eval_fail_report")
    g.add_edge("eval_fail_report", END)   # 失败时：输出诊断报告后终止
    g.add_edge("store", "compliance_export")
    g.add_edge("compliance_export", END)
    return g.compile()

# eval_fail_report_node 示例：将 eval_report 写入本地 JSON 并打印摘要
def eval_fail_report_node(state: PipelineState) -> PipelineState:
    """评测不达标时输出诊断报告（F1/P/R 数值、失败阈值、样本数）。
    写入 eval/baselines/<textbook_id>_fail_<timestamp>.json 供 CI 日志收集。
    """
    import json, pathlib, datetime
    report = state.get("eval_report", {})
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out = pathlib.Path(f"eval/baselines/{state['textbook_id']}_fail_{ts}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"[eval_gate FAILED] report → {out}\n{json.dumps(report, ensure_ascii=False)}")
    return state
```

- [ ] **Step 2: 并行抽取**（asyncio + maxConcurrency）+ 章节级失败重试 3 次

- [ ] **Step 3: 集成测试（mock 全链）+ 提交**

---

### Task 10: 评测 Harness（CI 准入门槛）

**Files:**
- Create: `eval/kg_extraction_500.jsonl`（先生成 50 条样本，后续众包扩充到 500）
- Create: `src/eval/runner.py`
- Create: `src/eval/metrics.py`
- Create: `.github/workflows/eval.yml`

> ⚠️ **P1-5 统计可靠性说明**：50 条样本下三元组 F1 的 95% 置信区间约 ±0.14，门槛 0.80 在统计上不可靠。分阶段策略：
> - **阶段 1**（样本 < 200）：CI 仅输出警告，不 block PR；F1 警告线 0.65
> - **阶段 2**（样本 200-499）：CI block 门槛 0.72（±0.07 区间的保守下界）
> - **阶段 3**（样本 ≥ 500）：CI block 门槛 0.80（目标值）

- [ ] **Step 1: 评测样本格式**

```jsonl
{"chapter_text": "...", "expected_triples": [{"subject":"三角形","predicate":"is_a","object":"几何图形"}, ...]}
```

- [ ] **Step 2: 指标实现**

```python
# src/eval/metrics.py — 三元组级 P/R/F1（实体名归一化 + 同义词容忍）
def triple_prf(pred, gold) -> dict:
    ...
```

- [ ] **Step 3: Runner**

```python
# src/eval/runner.py
def run_eval(extractor, dataset_path: str) -> dict:
    # 跑全集 → 计算 P/R/F1 → 与 baseline 对比 → 写 eval/baselines/<sha>.json
    ...
```

- [ ] **Step 4: GitHub Actions**

```yaml
# .github/workflows/eval.yml — PR 触发，分阶段门槛（见 P1-5 说明）
# 样本 < 200：warning only；200-499：block F1 < 0.72；≥ 500：block F1 < 0.80
```

- [ ] **Step 5: 提交**

```bash
git add eval src/eval .github/workflows/eval.yml
git commit -m "feat: 评测 harness + CI 准入门槛 F1 ≥ 0.80"
```

---

### Task 11: DSPy 编译式 Prompt 优化（可选但推荐）

> ⚠️ **P2-3 跳过路径说明**：若跳过 Task 11，需在 Task 10 阶段 1（样本 50 条）确认基础模型 F1 ≥ 0.65，否则 CI 阶段 2 的 0.72 门槛将无法达到。如果基础 F1 < 0.65，Task 11 从"可选"升级为**必须执行**。

**Files:**
- Create: `src/eval/dspy_optimize.py`

- [ ] **Step 1: 用 100 条评测样本跑 MIPROv2 自动优化 Domain 抽取 prompt + few-shot**
- [ ] **Step 2: 优化前后 F1 对比报告**
- [ ] **Step 3: 优化产物（编译后的 prompt）入版本控制**

---

### Task 12: 端到端集成、运行脚本与 README

**Files:**
- Create: `run_pipeline.py`
- Create: `README.md`
- Create: `tests/test_e2e.py`

- [ ] **Step 1: CLI**

```bash
python run_pipeline.py \
  --input book.pdf --textbook-id math-2026 --subject math \
  --neo4j-uri $NEO4J_URI --qdrant-url $QDRANT_URL \
  --eval-gate strict
```

- [ ] **Step 2: README**（环境变量、本地开发、评测、成本预算说明）
- [ ] **Step 3: E2E 测试（小规模教材样本走完全链）+ 提交**

---

### Task 13: JY/T 标准合规模块（基础教育知识图谱建设技术规范）

> **依据：** 《基础教育知识图谱建设技术规范》JY/T XXXX—XXXX（征求意见稿，2025-08-29），教育部科学技术与信息化司
>
> **设计原则：** 双层架构 —— 内部三层 KG（Neo4j，ML 优化）作为**运行层**；JY/T 标准本体作为**合规/互操作导出层**。两层解耦，互不替代。

**Files:**
- Create: `src/compliance/ontology_mapper.py`
- Create: `src/compliance/relation_mapper.py`
- Create: `src/compliance/rdf_exporter.py`
- Create: `src/compliance/validator.py`
- Create: `src/compliance/jyt_0644_codes.py`
- Create: `src/compliance/shacl_shapes.ttl`
- Update: `config/knowledge-graph.yaml` — 增加 `jyt_compliance` 节
- Update: `src/models/entities.py` — 为 Entity 增加 JY/T 合规字段

#### 13.1 本体映射设计

> **双层架构说明**：内部 `curriculum_standard_node` 在 JY/T 标准中没有直接对应的顶层类。JY/T §6.5.2 允许通过 `rdfs:subClassOf` 扩展，因此导出时将其映射到自定义类 `edukg:CurriculumRequirement`（继承 `edukg:DisciplinaryKeyCompetency`），而不是直接映射到 `DisciplinaryKeyCompetency`（该类在 JY/T 标准中专指"科学探究"等核心素养能力，有 `competencyType` 枚举约束，与课标内容要求节点语义不同）。

**内部实体 → JY/T 标准类的映射规则：**

| 内部实体类型 | JY/T 类 | 映射说明 |
|---|---|---|
| `concept / formula / theorem / dataset` | `edukg:LearningPoint` | 知识的最小单元；`cognitiveLevel` 从 bloom_level 翻译 |
| `textbook / chapter / section` | `edukg:EducationalMaterial` | 教学资料；`version/publisherName` 从元数据填充 |
| `Question`（题库） | `edukg:Question` | 题目类；`stem/answer/choices/analysis` 直接映射 |
| `learning_objective / lesson / activity` | `edukg:LearningActivity` | 学习活动；`plan/expectedResult` 从描述字段映射 |
| `curriculum_standard_node` | `edukg:CurriculumRequirement` ⚠️ | §6.5.2 扩展类，`rdfs:subClassOf edukg:DisciplinaryKeyCompetency`；不直接使用 `DisciplinaryKeyCompetency`（后者有 competencyType 枚举约束，语义不符） |
| 外部视频/网页资源 | `edukg:ExternalData` | `dataType/format/accessLink` 直接映射 |

**内部关系 → JY/T 标准关系的映射规则：**

| 内部关系 | JY/T 关系（`edukg:`） | 方向 | 说明 |
|---|---|---|---|
| `prerequisite_of` | `isPrerequisiteFor` | 同向 | 知识类内关系 |
| `skos:broader` | `hasChild`（交换主宾） | 反向 | A skos:broader B → B hasChild A |
| `skos:related` / `similar_to` | `isRelatedTo` | 同向 | 对称关系 |
| `skos:exactMatch` / `equivalent_to` | `isEquivalentTo` | 同向 | 强等价 |
| `includes` | `includes` | 同向 | 知识点包含 |
| `part_of` | `includes`（交换主宾） | 反向 | A part_of B → B includes A |
| `teaches` | `hasRelatedKnowledgePoint` | 同向 | 内部 lesson→concept 已是 resource→KP，无需交换主宾 |
| `assesses` | `hasRelatedQuestion` | 同向 | material → question |
| `addresses_misconception` | `contentJson` 记录 ⚠️ | — | RDF object property 不支持关系级标注；保留信息的方法是将 misconception 节点的 identifier 写入错误概念头部节点的 `contentJson` 字段（JSON 序列化），不生成独立 RDF 三元组 |
| `aligned_to` | `requiresKnowledgePoint` | 同向 | 素养/课标 → 知识点 |
| `textbook --contains--> chapter/section` | `hasSupplementaryEducationalMaterial` ⚠️ | 同向 | JY/T 标准无 contains 关系；`hasSubsequentEducationalMaterial` 是兄弟顺序关系（语义不符），此处用 `hasSupplementaryEducationalMaterial`（扩展资料）作为上下级教材层级的近似表达；若需精确，通过 §6.5.3 扩展 `includesChapter` 关系（继承 `DisciplinaryRelation`） |

**JY/T 0644 学科分类代码映射（`jyt_0644_codes.py`）：**

```python
# JY/T 0644 基础教育所属学科分类代码（部分）
SUBJECT_CODES = {
    "math":      "SB0101",   # 数学
    "physics":   "SB0303",   # 物理
    "chemistry": "SB0304",   # 化学
    "biology":   "SB0403",   # 生物
    "history":   "SB0501",   # 历史
    "geography": "SB0502",   # 地理
    "politics":  "SB0601",   # 政治/道德与法治
    "chinese":   "SB0201",   # 语文
    "english":   "SB0202",   # 英语
}

# JY/T 0644 学习者分类代码（学段）
LEVEL_CODES = {
    "primary_1_3":  "OB0301",   # 小学 1-3 年级
    "primary_4_6":  "OB0401",   # 小学 4-6 年级
    "junior_7_9":   "OB0601",   # 初中 7-9 年级
    "senior_10_12": "OB0701",   # 高中 10-12 年级
}
```

#### 13.2 实体模型字段扩充

在 `src/models/entities.py` 的 `Entity` 中新增 JY/T 合规字段（可选，仅在导出时填充）：

```python
from __future__ import annotations
from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field

class JYTCompliantFields(BaseModel):
    """JY/T XXXX 合规字段 —— 导出时填充，不影响内部存储"""
    identifier: str = Field(default_factory=lambda: str(uuid4()))  # UUID v4（§6.3 sh:pattern）
    title: str                                                       # 实体名称，sh:minCount 1
    subject: Optional[str] = None          # JY/T 0644 学科分类代码
    applicable_level: Optional[str] = None # JY/T 0644 学习者分类代码
    cognitive_level: Optional[str] = None  # 记忆/理解/应用/分析/评价/创造
    content_json: Optional[str] = None     # JSON 字符串，存储额外信息

# 注：Entity 已在 Task 2 中改为继承 EntityBase，下方仅展示 jyt 字段扩充位置。
# class Entity(EntityBase):         # 完整定义在 src/models/entities.py
#     ...（Task 2 内全量字段）
#     jyt: Optional[JYTCompliantFields] = None  # 标准合规扩展，懒填充
```

#### 13.3 RDF 序列化模块 (`src/compliance/rdf_exporter.py`)

```python
"""
rdf_exporter.py
将内部三层 KG（从 Neo4j 读取）导出为 JY/T 标准合规的 RDF 1.1 Turtle 文件
依赖：rdflib >= 7.0, pyshacl >= 0.25
"""
from rdflib import Graph, Namespace, RDF, RDFS, OWL, Literal, URIRef
from rdflib.namespace import XSD
import uuid

EDUKG = Namespace("http://edukg.org.cn/ontology#")
INSTANCE = Namespace("http://edukg.org.cn/instance#")

def build_graph(entities: list[dict], triples: list[dict]) -> Graph:
    g = Graph()
    g.bind("edukg", EDUKG)
    g.bind("owl", OWL)
    g.bind("xsd", XSD)

    # 注册 CurriculumRequirement 扩展类（§6.5.2）
    cr_class = EDUKG.CurriculumRequirement
    g.add((cr_class, RDF.type, OWL.Class))
    g.add((cr_class, RDFS.label, Literal("Curriculum Requirement")))
    g.add((cr_class, RDFS.comment, Literal("国家课程标准内容要求节点，继承自 DisciplinaryKeyCompetency")))
    g.add((cr_class, RDFS.subClassOf, EDUKG.DisciplinaryKeyCompetency))

    # misconception 反向索引：收集所有 addresses_misconception 三元组
    misconception_map: dict[str, list[str]] = {}   # concept_id → [misconception_id]
    for triple in triples:
        if triple["predicate"] == "addresses_misconception":
            concept_id = triple["subject_id"]
            mc_id = triple["object_id"]
            misconception_map.setdefault(concept_id, []).append(mc_id)

    for ent in entities:
        node = INSTANCE[ent["id"]]
        jyt_class = _map_to_jyt_class(ent["type"])
        g.add((node, RDF.type, jyt_class))
        g.add((node, EDUKG.identifier, Literal(ent.get("identifier", str(uuid.uuid4())))))
        g.add((node, EDUKG.title, Literal(ent["name"])))
        if ent.get("description"):
            g.add((node, EDUKG.description, Literal(ent["description"])))
        if ent.get("subject_code"):
            g.add((node, EDUKG.subject, Literal(ent["subject_code"])))
        if ent.get("applicable_level"):
            g.add((node, EDUKG.applicableLevel, Literal(ent["applicable_level"])))
        if ent.get("cognitive_level"):  # bloom_level → cognitiveLevel
            g.add((node, EDUKG.cognitiveLevel, Literal(ent["cognitive_level"])))
        # P0-4 修复：addresses_misconception 无法用 RDF 关系级标注，
        # 将相关 misconception id 列表序列化写入 contentJson
        mc_list = misconception_map.get(ent["id"], [])
        import json as _json
        base_json = _json.loads(ent["content_json"]) if ent.get("content_json") else {}
        if mc_list:
            base_json["addresses_misconception"] = mc_list
        if base_json:
            g.add((node, EDUKG.contentJson, Literal(_json.dumps(base_json, ensure_ascii=False))))

    for triple in triples:
        if triple["predicate"] == "addresses_misconception":
            continue  # 已处理到 contentJson，跳过生成三元组
        subj_id, obj_id = triple["subject_id"], triple["object_id"]
        subj = INSTANCE[subj_id]
        obj  = INSTANCE[obj_id]
        result = _map_to_jyt_relation(triple["predicate"])
        if result is None:
            continue
        pred, swap = result
        if swap:
            g.add((obj, pred, subj))   # 交换主宾
        else:
            g.add((subj, pred, obj))

    return g

def _map_to_jyt_class(internal_type: str) -> URIRef:
    mapping = {
        "concept": EDUKG.LearningPoint, "formula": EDUKG.LearningPoint,
        "theorem": EDUKG.LearningPoint, "dataset": EDUKG.LearningPoint,
        "textbook": EDUKG.EducationalMaterial, "chapter": EDUKG.EducationalMaterial,
        "section": EDUKG.EducationalMaterial,
        "learning_objective": EDUKG.LearningActivity, "lesson": EDUKG.LearningActivity,
        "activity": EDUKG.LearningActivity,
        # misconception 暂无 JY/T 直接对应类，映射到 LearningPoint（作为知识错误表征）
        "misconception": EDUKG.LearningPoint,
        # P0-3 修复：使用 §6.5.2 扩展类而非 DisciplinaryKeyCompetency 本身
        "curriculum_standard_node": EDUKG.CurriculumRequirement,
    }
    return mapping.get(internal_type, EDUKG.LearningPoint)

def _map_to_jyt_relation(internal_rel: str) -> tuple[URIRef, bool] | None:
    """返回 (jyt_predicate, swap_subject_object)。swap=True 表示需要交换主宾。"""
    mapping = {
        "prerequisite_of":  (EDUKG.isPrerequisiteFor,  False),
        # P0-2 修复：skos:broader / is_a 需要交换主宾（A broader B → B hasChild A）
        "is_a":             (EDUKG.hasChild,            True),
        "skos:broader":     (EDUKG.hasChild,            True),
        "skos:related":     (EDUKG.isRelatedTo,         False),
        "skos:exactMatch":  (EDUKG.isEquivalentTo,      False),
        "equivalent_to":    (EDUKG.isEquivalentTo,      False),
        "includes":         (EDUKG.includes,            False),
        # part_of 是 includes 的反向
        "part_of":          (EDUKG.includes,            True),
        # teaches 内部方向 lesson→concept（lesson=资源, concept=KP）
        # JY/T 要求 resource→KP，方向已匹配，无需交换主宾
        "teaches":          (EDUKG.hasRelatedKnowledgePoint, False),
        "assesses":         (EDUKG.hasRelatedQuestion,  False),
        "aligned_to":       (EDUKG.requiresKnowledgePoint, False),
        # P0-2 修复：contains 关系用 hasSupplementaryEducationalMaterial 近似；
        # 若需精确，在 jyt_ontology.ttl 中扩展 includesChapter 关系
        "contains":         (EDUKG.hasSupplementaryEducationalMaterial, False),
        # 未映射到 JY/T 标准关系的内部关系类型（有意略去）：
        # generalizes / contradicts / applies_to / before / after / defined_by / example_of
        # → JY/T 无直接对应，相关信息序列化写入对应节点的 contentJson 字段保留
        # addresses_misconception 在 build_graph 中通过 contentJson 处理，此处返回 None 跳过
    }
    return mapping.get(internal_rel)

def export_to_ttl(g: Graph, output_path: str) -> None:
    g.serialize(destination=output_path, format="turtle")
```

#### 13.4 标准合规验证模块 (`src/compliance/validator.py`)

实现 JY/T 标准 §8「证实方法」，逐项验证：

```python
"""
validator.py
§8 证实方法实现：
  a) JSON 格式验证（UTF-8 + RFC 8259 语法）
  b) RDF 1.1 格式验证（UTF-8 + rdflib 解析）
  c) 扩展类继承验证（§6.5.2，必须继承七个顶层类之一）
  d) 扩展属性继承验证（§6.5.3，必须继承 DisciplinaryAttribute）
  e) 扩展关系继承验证（§6.5.4，必须继承 DisciplinaryRelation）
  f) 必填字段验证（identifier UUID 格式 + title sh:minCount 1）
"""
import json, pathlib, re, uuid
from rdflib import Graph, RDF, RDFS, OWL, URIRef
from pyshacl import validate as shacl_validate

BASE = "http://edukg.org.cn/ontology#"
ALLOWED_CLASSES = {f"{BASE}{c}" for c in [
    "LearningPoint", "EducationalMaterial", "Question",
    "LearningActivity", "LearningResource", "ExternalData",
    "DisciplinaryKeyCompetency",
]}
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

class ComplianceReport:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def is_compliant(self) -> bool:
        return len(self.errors) == 0

def validate_json_file(path: str) -> ComplianceReport:
    """§8 a) JSON 格式验证"""
    report = ComplianceReport()
    p = pathlib.Path(path)
    try:
        raw = p.read_bytes()
        raw.decode("utf-8")
    except UnicodeDecodeError as e:
        report.errors.append(f"[UTF-8 编码错误] {e}")
        return report
    try:
        with p.open(encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        report.errors.append(f"[JSON 语法错误] 行 {e.lineno} 列 {e.colno}: {e.msg}")
    return report

def validate_rdf_file(path: str, fmt: str = "turtle") -> ComplianceReport:
    """§8 b) RDF 1.1 格式验证"""
    report = ComplianceReport()
    p = pathlib.Path(path)
    try:
        p.read_bytes().decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        report.errors.append(f"[UTF-8 编码错误] {e}")
        return report
    g = Graph()
    try:
        g.parse(str(p), format=fmt)
    except Exception as e:
        report.errors.append(f"[RDF 语法错误] {e}")
    return report

def validate_shacl(kg_path: str, shapes_path: str) -> ComplianceReport:
    """SHACL 约束验证（必填字段 + UUID 格式）"""
    report = ComplianceReport()
    kg_g = Graph().parse(kg_path, format="turtle")
    shapes_g = Graph().parse(shapes_path, format="turtle")
    conforms, _, text = shacl_validate(kg_g, shacl_graph=shapes_g)
    if not conforms:
        report.errors.append(f"[SHACL 违规] {text}")
    return report

def validate_class_inheritance(kg_path: str, ontology_path: str) -> ComplianceReport:
    """§8 c) 扩展类必须继承七个顶层类之一（支持多层传递继承）"""
    report = ComplianceReport()
    g = Graph().parse(kg_path, format="turtle")
    o = Graph().parse(ontology_path, format="turtle")
    ontology_classes = {str(c) for c in o.subjects(RDF.type, OWL.Class)}
    allowed = {URIRef(c) for c in ALLOWED_CLASSES}

    def has_allowed_ancestor(cls: URIRef, visited: set) -> bool:
        """DFS 查找 rdfs:subClassOf 链中是否存在允许的顶层类（防循环）"""
        if cls in visited:
            return False
        visited.add(cls)
        parents = list(g.objects(cls, RDFS.subClassOf))
        if any(p in allowed for p in parents):
            return True
        return any(has_allowed_ancestor(p, visited) for p in parents if isinstance(p, URIRef))

    for cls in g.subjects(RDF.type, OWL.Class):
        if str(cls) in ontology_classes:
            continue
        if not has_allowed_ancestor(cls, set()):
            report.errors.append(f"[类继承违规] {cls} 未继承七个允许类之一（包括传递）")
    return report

def validate_identifier_format(g: Graph) -> ComplianceReport:
    """验证所有实体的 identifier 符合 UUID 格式"""
    report = ComplianceReport()
    IDENTIFIER = URIRef(f"{BASE}identifier")
    for _, _, obj in g.triples((None, IDENTIFIER, None)):
        if not UUID_PATTERN.match(str(obj)):
            report.errors.append(f"[identifier 格式错误] '{obj}' 不符合 UUID v4 格式")
    return report
```

#### 13.5 SHACL 约束文件 (`src/compliance/shacl_shapes.ttl`)

```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix edukg: <http://edukg.org.cn/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# 公共必填字段：分别对每个实际顶层类定义 Shape（不能用不存在的 BaseEntity）
# 四个主要类共用同一约束高阶 shape，简化维护

# LearningPoint 必填字段 + UUID 格式
:LearningPointShape a sh:NodeShape ;
    sh:targetClass edukg:LearningPoint ;
    sh:property [
        sh:path edukg:identifier ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:pattern "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$" ;
        sh:message "identifier 必须为 UUID v4 格式" ;
    ] ;
    sh:property [
        sh:path edukg:title ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "title 为必填字段" ;
    ] ;
    sh:property [
        sh:path edukg:cognitiveLevel ;
        sh:in ("\u8bb0\u5fc6"^^xsd:string "\u7406\u89e3"^^xsd:string "\u5e94\u7528"^^xsd:string
               "\u5206\u6790"^^xsd:string "\u8bc4\u4ef7"^^xsd:string "\u521b\u9020"^^xsd:string) ;
        sh:message "cognitiveLevel 必须为六个 Bloom 层级之一" ;
    ] .

# EducationalMaterial 必填字段
:EducationalMaterialShape a sh:NodeShape ;
    sh:targetClass edukg:EducationalMaterial ;
    sh:property [
        sh:path edukg:identifier ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:pattern "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$" ;
        sh:message "identifier 必须为 UUID v4 格式" ;
    ] ;
    sh:property [
        sh:path edukg:title ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "title 为必填字段" ;
    ] .

# Question 必填字段
:QuestionShape a sh:NodeShape ;
    sh:targetClass edukg:Question ;
    sh:property [
        sh:path edukg:identifier ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:pattern "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$" ;
        sh:message "identifier 必须为 UUID v4 格式" ;
    ] ;
    sh:property [
        sh:path edukg:title ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "title 为必填字段" ;
    ] ;
    sh:property [
        sh:path edukg:stem ;
        sh:minCount 1 ;
        sh:message "试题必须有题干 stem" ;
    ] .

# LearningActivity 必填字段
:LearningActivityShape a sh:NodeShape ;
    sh:targetClass edukg:LearningActivity ;
    sh:property [
        sh:path edukg:identifier ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:pattern "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$" ;
        sh:message "identifier 必须为 UUID v4 格式" ;
    ] ;
    sh:property [
        sh:path edukg:title ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "title 为必填字段" ;
    ] .
```

#### 13.6 构建流水线集成

在 `agents/lead_agent.py` 中，在 Neo4j 存储节点**之后**增加条件导出节点。顺序与 Task 9 一致：

```
... 现有节点 ...
  ↓
evalGate（F1 评测闸值判断）
  ↓ [eval_passed == True]
Neo4j + Qdrant 双写（Task 8）
  ↓
[条件] if config.jyt_compliance.enabled:
  ↓
JY/T 合规导出节点（compliance_export_node）
  ├─ OntologyMapper：内部实体 → JY/T 类实例
  ├─ RelationMapper：内部关系 → JY/T 关系
  ├─ RDFExporter：rdflib 构建 Graph → .ttl 输出
  └─ Validator：§8 全量合规验证 → 生成 compliance_report.json
  ↓
END
```

**导出幂等性保证**：每次构建后覆盖写 `.ttl`，内容由 Neo4j snapshot 确定性生成；不引入额外存储状态。

#### 13.7 config 新增节

在 `config/knowledge-graph.yaml` 末尾添加：

```yaml
jyt_compliance:
  enabled: true                   # 构建完成后自动导出 JY/T 合规 .ttl
  ontology_url: "http://edukg.org.cn/ontology#"
  instance_url: "http://edukg.org.cn/instance#"
  output_path: "output/{textbook_id}_jyt.ttl"
  shacl_shapes: "src/compliance/shacl_shapes.ttl"
  ontology_file: "src/compliance/jyt_ontology.ttl"  # 从标准附录B生成
  subject_code_map: "src/compliance/jyt_0644_codes.py"
  validation:
    fail_on_error: false          # 合规违规记录到 report，不阻断主流程
    report_path: "output/{textbook_id}_compliance_report.json"
  bloom_to_cognitive:             # 内部 bloom_level → 标准 cognitiveLevel
    remember:  "记忆"
    understand: "理解"
    apply:     "应用"
    analyze:   "分析"
    evaluate:  "评价"
    create:    "创造"
```

#### 13.8 实现步骤

- [ ] **Step 1**: 生成 `jyt_ontology.ttl` — 将标准附录 B 中八个顶层类、标准属性和标准关系以 OWL/RDF Turtle 格式声明，作为 `validate_class_inheritance` 和 `validate_shacl` 的 ground truth 本体。最小实现应包含：
  ```turtle
  # src/compliance/jyt_ontology.ttl （最小骨干）
  @prefix owl: <http://www.w3.org/2002/07/owl#> .
  @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
  @prefix edukg: <http://edukg.org.cn/ontology#> .

  edukg:LearningPoint         a owl:Class .
  edukg:EducationalMaterial   a owl:Class .
  edukg:Question              a owl:Class .
  edukg:LearningActivity      a owl:Class .
  edukg:LearningResource      a owl:Class .
  edukg:ExternalData          a owl:Class .
  edukg:DisciplinaryKeyCompetency a owl:Class .
  # 扩展类（§6.5.2）
  edukg:CurriculumRequirement a owl:Class ;
      rdfs:subClassOf edukg:DisciplinaryKeyCompetency ;
      rdfs:label "课程标准内容要求节点" .
  # 标准属性（部分）
  edukg:identifier   a owl:DatatypeProperty .
  edukg:title        a owl:DatatypeProperty .
  edukg:description  a owl:DatatypeProperty .
  edukg:subject      a owl:DatatypeProperty .
  edukg:contentJson  a owl:DatatypeProperty .
  edukg:cognitiveLevel a owl:DatatypeProperty .
  edukg:stem         a owl:DatatypeProperty .
  # 标准关系（部分）
  edukg:isPrerequisiteFor     a owl:ObjectProperty .
  edukg:hasChild              a owl:ObjectProperty .
  edukg:isRelatedTo           a owl:ObjectProperty .
  edukg:isEquivalentTo        a owl:ObjectProperty .
  edukg:includes              a owl:ObjectProperty .
  edukg:hasRelatedKnowledgePoint a owl:ObjectProperty .
  edukg:hasRelatedQuestion    a owl:ObjectProperty .
  edukg:requiresKnowledgePoint a owl:ObjectProperty .
  edukg:hasSupplementaryEducationalMaterial a owl:ObjectProperty .
  ```
- [ ] **Step 2**: 实现 `jyt_0644_codes.py` — 学科分类代码 + 学习者分类代码字典
- [ ] **Step 3**: 实现 `ontology_mapper.py` + `relation_mapper.py` — 按 §13.1 映射表编写
- [ ] **Step 4**: 实现 `rdf_exporter.py` — 从 Neo4j Cypher 查询读取 + rdflib 序列化
- [ ] **Step 5**: 编写 `shacl_shapes.ttl` — 必填字段、UUID 格式、枚举约束
- [ ] **Step 6**: 实现 `validator.py` — §8 a~e 五类证实方法
- [ ] **Step 7**: 在 `lead_agent.py` 中接入 `compliance_export_node`
- [ ] **Step 8**: 添加 `tests/test_compliance.py` — 用小规模测试图谱跑全量合规检验
- [ ] **Step 9**: 提交

```bash
git add src/compliance tests/test_compliance.py config/ && \
  git commit -m "feat: Task 13 JY/T 标准合规模块（本体映射 + RDF 导出 + §8 验证）"
```

---

### Task 14: 仲裁队列 + 增量更新机制（P1-2 / P1-4 补充）

> **背景**：架构图中提到两处人工仲裁入口（跨教材冲突、Node2Vec 链接预测），以及 spec §6.2 要求的"教材改版 diff 传播"，但此前没有对应实现任务。

**Files:**
- Create: `src/storage/arbitration_queue.py`
- Create: `src/storage/version_tracker.py`
- Create: `src/storage/incremental_updater.py`
- Create: `tests/test_incremental.py`
- Update: `docs/schema.md` — 补充 Postgres 表结构

#### 14.1 Postgres 表结构

```sql
-- 仲裁队列：收集需要人工确认的 KG 变更
CREATE TABLE arbitration_queue (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT NOT NULL,          -- 'conflict_detection' | 'link_prediction'
    triple_subj TEXT NOT NULL,
    triple_pred TEXT NOT NULL,
    triple_obj  TEXT NOT NULL,
    confidence  FLOAT,
    context     JSONB,                  -- 来源证据、冲突详情
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    reviewer    TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 教材版本表：每次构建记录版本信息
CREATE TABLE textbook_versions (
    textbook_id TEXT NOT NULL,
    version     TEXT NOT NULL,
    sha256      TEXT NOT NULL,          -- 教材 PDF hash
    built_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    node_count  INT,
    triple_count INT,
    PRIMARY KEY (textbook_id, version)
);

-- KG 差异表：教材改版时记录新增/删除/修改的三元组
CREATE TABLE kg_diff (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    textbook_id TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version  TEXT NOT NULL,
    op          TEXT NOT NULL,          -- 'add' | 'remove' | 'update'
    triple_subj TEXT,
    triple_pred TEXT,
    triple_obj  TEXT,
    propagated  BOOL NOT NULL DEFAULT FALSE,  -- 是否已传播到 Pedagogical/Diagnostic 层
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### 14.2 仲裁队列模块 (`src/storage/arbitration_queue.py`)

```python
"""
arbitration_queue.py
写入仲裁队列，供 Expert Reviewer API 消费
"""
from dataclasses import dataclass
from typing import Literal
import psycopg2, json

@dataclass
class ArbitrationItem:
    source: Literal["conflict_detection", "link_prediction"]
    triple_subj: str
    triple_pred: str
    triple_obj: str
    confidence: float | None
    context: dict

class ArbitrationQueue:
    def __init__(self, pg_conn_str: str):
        self.conn_str = pg_conn_str

    def push(self, item: ArbitrationItem) -> None:
        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO arbitration_queue
                       (source, triple_subj, triple_pred, triple_obj, confidence, context)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (item.source, item.triple_subj, item.triple_pred,
                     item.triple_obj, item.confidence, json.dumps(item.context))
                )

    def pending_count(self) -> int:
        with psycopg2.connect(self.conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM arbitration_queue WHERE status='pending'")
                return cur.fetchone()[0]
```

#### 14.3 增量更新模块 (`src/storage/incremental_updater.py`)

```python
"""
incremental_updater.py
教材改版时：计算 diff → 写 kg_diff 表 → 传播影响到 Pedagogical/Diagnostic 层
"""
from dataclasses import dataclass
from typing import Literal

@dataclass
class TripleDiff:
    op: Literal["add", "remove", "update"]
    subj: str; pred: str; obj: str

class IncrementalUpdater:
    def __init__(self, neo4j_driver, pg_conn_str: str):
        self.driver = neo4j_driver
        self.pg = pg_conn_str

    def compute_diff(self, textbook_id: str,
                     old_version: str, new_version: str) -> list[TripleDiff]:
        """对比同一 textbook_id 两个版本的 Neo4j 快照，返回三元组级 diff。"""
        # 实现：按 textbook_anchor.textbook_id + version 标签查询
        # 用集合差运算得到 add/remove；update = 同一 (subj, pred) 但 obj 变化
        ...

    def apply_diff(self, textbook_id: str,
                   from_ver: str, to_ver: str,
                   diffs: list[TripleDiff]) -> None:
        """写 kg_diff 表；触发 Pedagogical/Diagnostic 层级联更新。"""
        # 1. 批量写 kg_diff 表
        # 2. 对影响到 learning_objective 的 diff，标记相关 Pedagogical 节点为 stale
        # 3. 对影响到 skill 映射的 diff，重新运行 Skill Mapper（Task 5 节点）
        ...

    def propagate(self, textbook_id: str) -> None:
        """将 propagated=FALSE 的 diff 项传播到下游层并标记为已传播。"""
        ...
```

#### 14.4 接入主管线

在 `agents/lead_agent.py` 中：
- `store_node` 执行完毕后写 `textbook_versions` 记录；
- `fuse_node` 中冲突检测 → `ArbitrationQueue.push(source="conflict_detection")`；
- Node2Vec 链接预测通过门槛后 → `ArbitrationQueue.push(source="link_prediction")`；
- 对已有版本的教材：在 `parse_node` 之后插入 `diff_node`，检测版本变化并触发增量流程。

#### 14.5 实现步骤

- [ ] **Step 1**: 建 Postgres 表（`migrations/001_arbitration_version.sql`）
- [ ] **Step 2**: 实现 `arbitration_queue.py` + `version_tracker.py`
- [ ] **Step 3**: 实现 `incremental_updater.py`（compute_diff + apply_diff + propagate）
- [ ] **Step 4**: 在 `lead_agent.py` 中接入仲裁推送和增量分支
- [ ] **Step 5**: 测试（mock 两版本教材，验证 diff 计算和传播）+ 提交

```bash
git add src/storage migrations tests/test_incremental.py && \
  git commit -m "feat: Task 14 仲裁队列 + 增量更新机制"
```

| Spec 要求 | 本计划落点 |
|---|---|
| 三层 KG schema | Task 1, 2, 5, 8 |
| GraphRAG 社区摘要 | Task 7 |
| BGE-M3 + verifier 消歧 | Task 6（BGE-M3 与 Task 3 共享单例） |
| 推理模型分级路由 | Task 4 |
| Structured outputs 零解析失败 | Task 4, 5 |
| 公式 LaTeX + SymPy | Task 2, 3 |
| 章节锚定 | Task 2, 3, 8 |
| 跨教材冲突 → 仲裁队列 | **Task 14**（ArbitrationQueue + Postgres） |
| 教材改版增量更新 | **Task 14**（IncrementalUpdater + kg_diff 表） |
| 评测集 + 分阶段 CI 门槛 | Task 10（样本<200 warning；≥500 block F1<0.80） |
| Prompt caching + 成本预算 | Task 4, 配置 |
| DSPy MIPROv2 编译优化 | Task 11（基础 F1<0.65 时从可选升为必须） |
| JY/T 教育行业标准合规 | Task 13（本体映射 + RDF 导出 + §8 证实） |
| JY/T curriculum_standard 类扩展 | Task 13.1（CurriculumRequirement 继承 DisciplinaryKeyCompetency） |
| SHACL 必填字段 + 枚举约束 | Task 13.5 shacl_shapes.ttl |
| PPR 多跳推理 | ★ 查询时操作（属于 spec §6.3 检索层），不在构建管线 |

## 执行选项

**1. Subagent-Driven（推荐）** — 每个 Task 独立 subagent，task 间评审

**2. Inline Execution** — 当前会话连续执行，断点提交

**Which approach?**
