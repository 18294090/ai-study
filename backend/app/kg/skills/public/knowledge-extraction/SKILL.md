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