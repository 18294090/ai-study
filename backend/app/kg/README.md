# Knowledge Graph Pipeline

从教材 PDF 全自动提取结构化知识图谱，写入 Neo4j + Qdrant，并通过评估门控（F1 阈值）把关入库质量。

---

## 架构概览

```
PDF / DOCX / Image
      │
      ▼
  ┌──────────┐
  │  Parser  │  多后端：PyMuPDF / MinerU / Docling / Nougat / UniMERNet
  └──────────┘
      │  Textbook(chapters)
      ▼
  ┌───────────────────────────────────┐
  │          LangGraph Pipeline       │
  │  ┌────────────┐  ┌─────────────┐  │
  │  │  Domain    │  │ Pedagogical │  │  并发 + 指数退避重试（bounded_retry_gather）
  │  │  Extractor │  │   Tagger    │  │
  │  └────────────┘  └─────────────┘  │
  │         ┌──────────────┐          │
  │         │ Skill Mapper │          │
  │         └──────────────┘          │
  └───────────────────────────────────┘
      │  domain_triples + pedagogical + skills
      ▼
  ┌──────────────────┐
  │  Entity Resolver │  BGE-M3 多字段联合嵌入（name + type + description[:200]）
  │  + Verifier      │  结构化 LLM 输出解析，含文本回退
  └──────────────────┘
      │
      ▼
  ┌──────────────────────┐
  │ Contradiction Detect │  语义相似度三档阈值（SequenceMatcher / 余弦）
  └──────────────────────┘
      │
      ▼
  ┌──────────────────┐
  │ Community Detect │  Leiden 算法（GDS），幂等投影，自动清理内存图
  └──────────────────┘
      │
      ▼
  ┌────────────┐
  │ Eval Gate  │  triple-PRF（动态同义词 + 编辑距离 + 可选 BGE-M3）
  └────────────┘
      │ F1 通过
      ▼
  ┌──────────────┐
  │  DualWriter  │  Neo4j + Qdrant 双写，死信队列，失败回滚
  └──────────────┘
      │
      ▼
  ┌────────────────┐
  │ GraphRAG Query │  意图分类 → 混合检索 → Rerank → 生成 → Self-RAG 验证
  └────────────────┘
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j URI |
| `NEO4J_USER` | `neo4j` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | *(必填)* | Neo4j 密码 |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant URL |
| `QDRANT_API_KEY` | *(可选)* | Qdrant API Key |
| `OPENAI_API_KEY` | *(必填，或配置 vLLM)* | LLM API Key |

---

## 快速开始

### 前置依赖

- Python 3.12+
- Neo4j 5.x（需安装 **GDS 插件** 用于社区检测）
- Qdrant 1.x

### 配置环境

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_PASSWORD="your-password"
export QDRANT_URL="http://localhost:6333"
export OPENAI_API_KEY="sk-..."
```

### 运行流水线

```bash
python run_pipeline.py \
  --input book.pdf \
  --textbook-id math-2026 \
  --subject math \
  --neo4j-uri $NEO4J_URI \
  --qdrant-url $QDRANT_URL \
  --eval-gate strict
```

| 参数 | 说明 |
|------|------|
| `--input` | 输入 PDF 路径 |
| `--textbook-id` | 教材唯一标识（如 `math-2026`）|
| `--subject` | 学科（`math` / `physics` / `chemistry` 等）|
| `--eval-gate` | `strict` F1≥0.8 \| `relaxed` F1≥0.6 \| `permissive` F1≥0.4 |
| `--edition` | 教材版次（可选）|
| `--output-dir` | 输出目录（默认 `output/`）|

---

## 模块说明

### agents/

| 文件 | 功能 |
|------|------|
| `lead_agent.py` | LangGraph 主流水线编排，`bounded_retry_gather()` 公共并发重试工具（信号量 + 指数退避） |
| `domain_extractor.py` | 从章节文本抽取领域三元组（置信度 ≥ 0.8） |
| `pedagogical_tagger.py` | 标注 Bloom 层次 / 学习目标 / 常见误解 |
| `skill_mapper.py` | 生成 Q-Matrix 技能映射 |
| `verifier_agent.py` | 实体共指消歧：优先结构化 LLM 输出（`_VerificationSchema`），回退多模式文本解析 |
| `contradiction_detector.py` | 语义相似度矛盾检测（`SequenceMatcher` 三档阈值，取代粗糙长度比较） |
| `community_detector.py` | Leiden 社区检测（GDS），幂等 `gds.graph.exists` 投影管理 |
| `graphrag_service.py` | GraphRAG 查询服务（意图分类 → 混合检索 → Cohere Rerank → 生成 → Self-RAG 验证）|

### src/fusion/

| 文件 | 功能 |
|------|------|
| `embedder.py` | BGE-M3 嵌入封装，FlagEmbedding 不可用时优雅降级 |
| `entity_resolver.py` | `_entity_to_text()` 多字段联合嵌入聚类（name + type + description[:200]，ReFinED 最佳实践） |

### src/storage/

| 文件 | 功能 |
|------|------|
| `dual_writer.py` | Neo4j + Qdrant 双写，死信队列，失败自动回滚 |
| `incremental_updater.py` | 版本间三元组差分（参数化 Cypher `$textbook_id`/`$version`，防 Cypher 注入） |
| `version_tracker.py` | PostgreSQL 教材版本记录 |
| `arbitration_queue.py` | 人工仲裁队列 |

### src/eval/

| 文件 | 功能 |
|------|------|
| `metrics.py` | triple-PRF；`register_synonyms()` 动态同义词注册；`SequenceMatcher` 编辑距离（阈值 0.82）；可选 BGE-M3 余弦（阈值 0.88）；懒加载嵌入器 |
| `runner.py` | 批量评估执行器 |

### src/compliance/

JYT-0644 国标本体合规：SHACL 验证（PySHACL）、RDF 导出（RDFLib）、领域关系映射。

---

## 评估

```bash
python -m pytest tests/ -v
```

- **Precision**：预测三元组中正确的比例
- **Recall**：金标三元组中被召回的比例
- **F1**：调和平均

### 参考成本（OpenAI GPT-4o）

| 操作 | 估算成本（美元） |
|------|----------------|
| PDF 解析 | $0.02 |
| 领域抽取（每 1K 词）| $0.15 |
| 教学标注（每 1K 词）| $0.10 |
| 技能映射（每 1K 词）| $0.10 |
| 评估门控 | $0.01 |

**每章估算总计**：~$0.40

## Architecture

```
Input PDF
    │
    ▼
┌─────────┐
│  Parse  │
└─────────┘
    │
    ▼
┌──────────────────┐
│ Extract Domain    │
│ Tag Pedagogical   │
│ Map Skills        │
└──────────────────┘
    │
    ▼
┌─────────┐
│  Fuse   │
└─────────┘
    │
    ▼
┌─────────────┐
│   Verify    │
└─────────────┘
    │
    ▼
┌──────────────────┐
│ Detect Communities│
└──────────────────┘
    │
    ▼
┌───────────┐
│ Eval Gate │
└───────────┘
    │
    ▼
┌─────────┐     ┌────────────────┐
│  Store  │────►│ Compliance Exp │
└─────────┘     └────────────────┘
```

## Testing

```bash
python -m pytest tests/ -v
```
