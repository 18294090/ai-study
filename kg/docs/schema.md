<<<<<<< HEAD
# Database Schema

## PostgreSQL Tables

### arbitration_queue

Collects knowledge graph changes that require human arbitration.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Unique identifier |
| `source` | `TEXT` | `NOT NULL` | Origin of the item: `conflict_detection` or `link_prediction` |
| `triple_subj` | `TEXT` | `NOT NULL` | Subject entity URI |
| `triple_pred` | `TEXT` | `NOT NULL` | Predicate URI |
| `triple_obj` | `TEXT` | `NOT NULL` | Object entity URI |
| `confidence` | `FLOAT` | | Confidence score from detection system |
| `context` | `JSONB` | | Source evidence and conflict details |
| `status` | `TEXT` | `NOT NULL`, `DEFAULT 'pending'` | `pending`, `approved`, or `rejected` |
| `reviewer` | `TEXT` | | Username of reviewer |
| `reviewed_at` | `TIMESTAMPTZ` | | Timestamp of review |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT now()` | Creation timestamp |

### textbook_versions

Records version information for each textbook build.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `textbook_id` | `TEXT` | `NOT NULL` | Textbook identifier |
| `version` | `TEXT` | `NOT NULL` | Version string |
| `sha256` | `TEXT` | `NOT NULL` | PDF hash for content verification |
| `built_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT now()` | Build timestamp |
| `node_count` | `INT` | | Number of nodes in KG |
| `triple_count` | `INT` | | Number of triples in KG |
| | | | `PRIMARY KEY (textbook_id, version)` |

### kg_diff

Records added/removed/modified triples when textbooks are updated.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY`, `DEFAULT gen_random_uuid()` | Unique identifier |
| `textbook_id` | `TEXT` | `NOT NULL` | Textbook identifier |
| `from_version` | `TEXT` | `NOT NULL` | Previous version |
| `to_version` | `TEXT` | `NOT NULL` | New version |
| `op` | `TEXT` | `NOT NULL` | Operation: `add`, `remove`, or `update` |
| `triple_subj` | `TEXT` | | Subject entity URI |
| `triple_pred` | `TEXT` | | Predicate URI |
| `triple_obj` | `TEXT` | | Object entity URI |
| `propagated` | `BOOL` | `NOT NULL`, `DEFAULT FALSE` | Whether diff has been propagated to Ped/Diag layers |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, `DEFAULT now()` | Creation timestamp |

## SQL Schema Definition

```sql
-- 仲裁队列：收集需要人工确认的 KG 变更
CREATE TABLE arbitration_queue (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT NOT NULL,
    triple_subj TEXT NOT NULL,
    triple_pred TEXT NOT NULL,
    triple_obj  TEXT NOT NULL,
    confidence  FLOAT,
    context     JSONB,
    status      TEXT NOT NULL DEFAULT 'pending',
    reviewer    TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 教材版本表：每次构建记录版本信息
CREATE TABLE textbook_versions (
    textbook_id TEXT NOT NULL,
    version     TEXT NOT NULL,
    sha256      TEXT NOT NULL,
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
    op          TEXT NOT NULL,
    triple_subj TEXT,
    triple_pred TEXT,
    triple_obj  TEXT,
    propagated  BOOL NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
=======
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
>>>>>>> feature/kg-module
