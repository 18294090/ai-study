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