# KG Operational Enhancements: OpLog + Contradiction + Lint

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为知识图谱添加操作日志、矛盾检测、Lint健康检查三个运维机制。

**Architecture:**
- `Neo4jWriter` 新增 `log_operation()` 方法，每次写操作后同步写入 OperationLog 节点
- `ContradictionDetector` 在 `fuse_node` 前检测新三元组与已有KG的矛盾，severity≥0.5入ExpertReviewer队列
- `KGLinter` 定时/手动检查孤立节点、陈旧关系、死链接，输出 health_score

**Tech Stack:** Neo4j (Cypher), Pydantic, FastAPI, Python

---

## File Map

### New Files
- `backend/app/kg/agents/contradiction_detector.py` — 矛盾检测
- `backend/app/kg/agents/kg_linter.py` — 健康检查
- `backend/tests/unit/kg/agents/test_contradiction_detector.py`
- `backend/tests/unit/kg/agents/test_kg_linter.py`

### Modified Files
- `backend/app/kg/src/storage/neo4j_writer.py` — 新增 `log_operation()`
- `backend/app/kg/agents/lead_agent.py` — fuse_node 前插入矛盾检测

---

## Task 1: Add log_operation to Neo4jWriter

**Files:**
- Modify: `backend/app/kg/src/storage/neo4j_writer.py`
- Test: `backend/tests/unit/kg/agents/test_oplog.py`

- [ ] **Step 1: Read current neo4j_writer.py**

- [ ] **Step 2: Add log_operation method and schema init**

Add this method after `write_community()` (around line 225):

```python
    def log_operation(
        self,
        operation: str,
        target_id: str,
        target_type: str,
        user_id: str = "system",
        details: str = "{}",
        textbook_id: str = None,
        reasoning: str = "",
    ) -> bool:
        with self._driver.session(database=self.database) as session:
            cypher = """
            CREATE (l:OperationLog {
                timestamp: datetime(),
                operation: $operation,
                target_id: $target_id,
                target_type: $target_type,
                user_id: $user_id,
                details: $details,
                textbook_id: $textbook_id,
                reasoning: $reasoning
            })
            RETURN l
            """
            session.run(
                cypher,
                operation=operation,
                target_id=target_id,
                target_type=target_type,
                user_id=user_id,
                details=details,
                textbook_id=textbook_id,
                reasoning=reasoning,
            )
        return True

    def init_oplog_schema(self):
        with self._driver.session(database=self.database) as session:
            session.run("CREATE INDEX FOR (l:OperationLog) ON (l.timestamp) IF NOT EXISTS")
            session.run("CREATE INDEX FOR (l:OperationLog) ON (l.target_id) IF NOT EXISTS")
            session.run("CREATE INDEX FOR (l:OperationLog) ON (l.operation) IF NOT EXISTS")
        logger.info("OperationLog schema ensured")

    def init_schema(self):
        with self._driver.session(database=self.database) as session:
            self._ensure_constraints(session)
            self.init_oplog_schema()
```

- [ ] **Step 3: Call log_operation in write_entity**

Find `write_entity` (line 87) and add after `session.run(cypher, props=props)` (line 101):

```python
        self.log_operation(
            operation="create_entity",
            target_id=entity.id,
            target_type="entity",
            user_id=getattr(entity, "created_by", "system"),
            details=entity.model_dump_json(),
            textbook_id=getattr(entity.anchor, "textbook_id", None) if entity.anchor else None,
        )
```

- [ ] **Step 4: Call log_operation in write_triple**

Find `write_triple` (line 130) and add before `return True` (after line 172):

```python
        self.log_operation(
            operation="create_triple",
            target_id=f"{triple.subject.id}-{triple.predicate.value}-{triple.object.id}",
            target_type="triple",
            user_id=triple.extracted_by or "system",
            details=triple.model_dump_json(),
            textbook_id=getattr(triple.anchor, "textbook_id", None) if triple.anchor else None,
        )
```

- [ ] **Step 5: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.src.storage.neo4j_writer import Neo4jWriter; print('Neo4jWriter with log_operation OK')"
```

- [ ] **Step 6: Commit**

---

## Task 2: Create ContradictionDetector

**Files:**
- Create: `backend/app/kg/agents/contradiction_detector.py`
- Test: `backend/tests/unit/kg/agents/test_contradiction_detector.py`

- [ ] **Step 1: Write the file**

```python
# backend/app/kg/agents/contradiction_detector.py
from __future__ import annotations
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel
import json


class Contradiction(BaseModel):
    type: str
    triple_a_id: str
    triple_b_id: str
    severity: float
    resolution: str  # "keep_new" | "keep_old" | "flag_for_review" | "merge"
    description: str


@dataclass
class ContradictionDetector:
    neo4j_driver: any

    def detect(self, new_triples: List[Any], textbook_id: str) -> List[Contradiction]:
        contradictions = []

        for nt in new_triples:
            conflicts = self._check_entity_conflicts(nt, textbook_id)
            contradictions.extend(conflicts)

            relation_conflicts = self._check_relation_conflicts(nt, textbook_id)
            contradictions.extend(relation_conflicts)

        return contradictions

    def _check_entity_conflicts(self, triple: Any, textbook_id: str) -> List[Contradiction]:
        conflicts = []
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (e {id: $id}) WHERE e.textbook_id <> $textbook_id "
                    "RETURN e.id AS id, e.name AS name, e.description AS desc, e.textbook_id AS source",
                    id=triple.subject.id, textbook_id=textbook_id
                )
                existing = result.data()
                if existing:
                    for e in existing:
                        if abs(len(triple.subject.description or "") - len(e["desc"] or "")) > 500:
                            conflicts.append(Contradiction(
                                type="entity_conflict",
                                triple_a_id=triple.subject.id,
                                triple_b_id=e["id"],
                                severity=0.6,
                                resolution="flag_for_review",
                                description=f"实体 {triple.subject.name} 与已有版本描述差异大（来源: {e['source']}）"
                            ))
        except Exception:
            pass
        return conflicts

    def _check_relation_conflicts(self, triple: Any, textbook_id: str) -> List[Contradiction]:
        conflicts = []
        if triple.predicate.value not in ("is_a", "part_of", "contradicts"):
            return conflicts

        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                inverse_pred = self._get_inverse_predicate(triple.predicate.value)
                if inverse_pred:
                    result = session.run(
                        "MATCH (s)-[r:%s]->(o) WHERE s.id = $sid AND o.id = $oid AND type(r) = $inverse "
                        "RETURN r.predicate AS existing_rel",
                        sid=triple.object.id, oid=triple.subject.id, inverse=inverse_pred
                    )
                    data = result.data()
                    if data:
                        conflicts.append(Contradiction(
                            type="relation_conflict",
                            triple_a_id=f"{triple.subject.id}-{triple.predicate.value}-{triple.object.id}",
                            triple_b_id=f"{triple.object.id}-{inverse_pred}-{triple.subject.id}",
                            severity=0.7,
                            resolution="flag_for_review",
                            description=f"关系方向冲突：{triple.subject.name} --[{triple.predicate.value}]--> {triple.object.name} vs 反向已有关系"
                        ))
        except Exception:
            pass
        return conflicts

    def _get_inverse_predicate(self, pred: str) -> Optional[str]:
        inverse_map = {
            "is_a": "is_a",
            "part_of": "contains",
            "requires": "enables",
            "causes": "result_of",
        }
        return inverse_map.get(pred)

    def resolve(self, contradiction: Contradiction) -> str:
        if contradiction.severity < 0.5:
            return contradiction.resolution
        return "flag_for_review"
```

- [ ] **Step 2: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.contradiction_detector import ContradictionDetector, Contradiction; print('ContradictionDetector OK')"
```

- [ ] **Step 3: Commit**

---

## Task 3: Create KGLinter

**Files:**
- Create: `backend/app/kg/agents/kg_linter.py`
- Test: `backend/tests/unit/kg/agents/test_kg_linter.py`

- [ ] **Step 1: Write the file**

```python
# backend/app/kg/agents/kg_linter.py
from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel


class KGIssue(BaseModel):
    type: str  # "orphan_node" | "stale_relation" | "dead_citation" | "inconsistent_type"
    node_id: str
    description: str
    severity: float  # 0-1


class KGHealthReport(BaseModel):
    total_nodes: int
    total_edges: int
    issues: List[KGIssue]
    health_score: float
    checked_at: str


@dataclass
class KGLinter:
    neo4j_driver: any

    def check(self, textbook_id: str = None) -> KGHealthReport:
        issues = []

        issues.extend(self._find_orphan_nodes(textbook_id))
        issues.extend(self._find_stale_relations(textbook_id))
        issues.extend(self._find_dead_citations(textbook_id))

        from datetime import datetime, timezone
        checked_at = datetime.now(timezone.utc).isoformat()

        total = self._count_nodes(textbook_id)
        health_score = 1.0 - len(issues) / max(total, 1)

        return KGHealthReport(
            total_nodes=total,
            total_edges=self._count_edges(textbook_id),
            issues=issues,
            health_score=max(health_score, 0.0),
            checked_at=checked_at,
        )

    def _count_nodes(self, textbook_id: str = None) -> int:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                if textbook_id:
                    result = session.run(
                        "MATCH (n) WHERE n.textbook_id = $tid RETURN count(n) as c",
                        tid=textbook_id
                    )
                else:
                    result = session.run("MATCH (n) RETURN count(n) as c")
                return result.single()["c"]
        except Exception:
            return 0

    def _count_edges(self, textbook_id: str = None) -> int:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                if textbook_id:
                    result = session.run(
                        "MATCH ()-[r]->() WHERE r.textbook_id = $tid RETURN count(r) as c",
                        tid=textbook_id
                    )
                else:
                    result = session.run("MATCH ()-[r]->() RETURN count(r) as c")
                return result.single()["c"]
        except Exception:
            return 0

    def _find_orphan_nodes(self, textbook_id: str = None) -> List[KGIssue]:
        issues = []
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                query = (
                    "MATCH (n) "
                    "WHERE NOT (n)-[]->() AND NOT ()-[]->(n) "
                    "RETURN n.id AS id, n.name AS name LIMIT 50"
                )
                if textbook_id:
                    query = (
                        "MATCH (n) WHERE n.textbook_id = $tid "
                        "AND NOT (n)-[]->() AND NOT ()-[]->(n) "
                        "RETURN n.id AS id, n.name AS name LIMIT 50"
                    )
                    result = session.run(query, tid=textbook_id)
                else:
                    result = session.run(query)
                for record in result:
                    issues.append(KGIssue(
                        type="orphan_node",
                        node_id=record["id"],
                        description=f"孤立节点: {record['name']}（入度=出度=0）",
                        severity=0.3,
                    ))
        except Exception:
            pass
        return issues

    def _find_stale_relations(self, textbook_id: str = None) -> List[KGIssue]:
        issues = []
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                query = (
                    "MATCH (s)-[r]->(o) "
                    "WHERE r.textbook_id = $tid AND r.extracted_by IS NOT NULL "
                    "WITH s, r, o, r.extracted_by AS eb "
                    "WHERE eb IS NOT NULL "
                    "RETURN s.id AS sid, o.id AS oid, r.predicate AS rel LIMIT 50"
                )
                result = session.run(query, tid=textbook_id or "")
                for record in result:
                    issues.append(KGIssue(
                        type="stale_relation",
                        node_id=f"{record['sid']}-{record['rel']}-{record['oid']}",
                        description=f"可能陈旧关系（来自教材 {textbook_id}）",
                        severity=0.2,
                    ))
        except Exception:
            pass
        return issues

    def _find_dead_citations(self, textbook_id: str = None) -> List[KGIssue]:
        issues = []
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (n) WHERE n.reference_textbook_id IS NOT NULL "
                    "AND NOT (n)-[]->() "
                    "RETURN n.id AS id, n.name AS name LIMIT 50"
                )
                for record in result:
                    issues.append(KGIssue(
                        type="dead_citation",
                        node_id=record["id"],
                        description=f"死链接: {record['name']} 被引用但无出站关系",
                        severity=0.4,
                    ))
        except Exception:
            pass
        return issues
```

- [ ] **Step 2: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.kg_linter import KGLinter, KGHealthReport, KGIssue; print('KGLinter OK')"
```

- [ ] **Step 3: Commit**

---

## Task 4: Integrate ContradictionDetector into lead_agent

**Files:**
- Modify: `backend/app/kg/agents/lead_agent.py`

- [ ] **Step 1: Read lead_agent.py, find the fuse_node function**

Locate the `fuse_node` function (around line 127-129).

- [ ] **Step 2: Add contradiction_check before fuse_node**

In the `build_graph()` function, add a new node `check_contradictions`:

Find the current graph edges:
```python
g.add_edge("extract_domain", "fuse")
g.add_edge("tag_pedagogical", "fuse")
g.add_edge("map_skills", "fuse")
```

Change to:
```python
g.add_edge("extract_domain", "check_contradictions")
g.add_edge("tag_pedagogical", "check_contradictions")
g.add_edge("map_skills", "check_contradictions")
g.add_edge("check_contradictions", "fuse")
```

Add this function before `build_graph()`:

```python
def check_contradictions_node(state: PipelineState) -> PipelineState:
    from kg.agents.contradiction_detector import ContradictionDetector
    from kg.src.storage.neo4j_writer import Neo4jWriter
    import os

    cfg = get_config()
    neo4j_cfg = cfg.storage.get("neo4j", {})
    neo4j_driver = Neo4jWriter(
        uri=os.environ.get(neo4j_cfg.get("uri_env", "NEO4J_URI"), "bolt://localhost:7687"),
        user=os.environ.get(neo4j_cfg.get("user_env", "NEO4J_USER"), "neo4j"),
        password=os.environ.get(neo4j_cfg.get("password_env", "NEO4J_PASSWORD"), ""),
    )

    triples = state.get("domain_triples", [])
    if not triples:
        return state

    textbook_id = state.get("textbook_id", "")
    detector = ContradictionDetector(neo4j_driver=neo4j_driver._driver)
    contradictions = detector.detect(triples, textbook_id)

    high_severity = [c for c in contradictions if c.severity >= 0.5]
    if high_severity:
        print(f"[contradiction] {len(high_severity)} contradictions flagged for review")

    state["contradictions"] = [c.model_dump() for c in contradictions]
    return state
```

Add node to graph in `build_graph()`:
```python
g.add_node("check_contradictions", check_contradictions_node)
```

- [ ] **Step 3: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.kg.agents.lead_agent import build_graph; g = build_graph(); print('lead_agent with contradiction check OK'); print('Nodes:', list(g.nodes))"
```

- [ ] **Step 4: Commit**

---

## Task 5: Add Lint API endpoint

**Files:**
- Create: `backend/app/api/v1/routes/kg_health.py`
- Test: `backend/tests/integration/kg/test_kg_health.py`

- [ ] **Step 1: Write the file**

```python
# backend/app/api/v1/routes/kg_health.py
from fastapi import APIRouter, Depends, HTTPException
from app.core.auth import get_current_user
from app.models.user import User
from kg.agents.kg_linter import KGLinter
from kg.src.storage.neo4j_writer import Neo4jWriter
from app.core.config import settings
import os

router = APIRouter()


def get_neo4j_writer() -> Neo4jWriter:
    return Neo4jWriter(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", ""),
    )


@router.get("/kg/health", operation_id="KG健康检查")
async def kg_health_check(
    textbook_id: str = None,
    current_user: User = Depends(get_current_user),
):
    writer = get_neo4j_writer()
    linter = KGLinter(neo4j_driver=writer._driver)
    report = linter.check(textbook_id)
    return {
        "total_nodes": report.total_nodes,
        "total_edges": report.total_edges,
        "health_score": report.health_score,
        "issues_count": len(report.issues),
        "issues": [i.model_dump() for i in report.issues[:20]],
        "checked_at": report.checked_at,
    }


@router.get("/kg/operations", operation_id="查询操作日志")
async def get_operations(
    target_id: str = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    writer = get_neo4j_writer()
    try:
        with writer._driver.session(database="neo4j") as session:
            if target_id:
                result = session.run(
                    "MATCH (l:OperationLog) WHERE l.target_id = $tid "
                    "RETURN l.timestamp AS ts, l.operation AS op, l.target_id AS tid, "
                    "l.user_id AS uid, l.reasoning AS reason "
                    "ORDER BY ts DESC LIMIT $limit",
                    tid=target_id, limit=limit
                )
            else:
                result = session.run(
                    "MATCH (l:OperationLog) "
                    "RETURN l.timestamp AS ts, l.operation AS op, l.target_id AS tid, "
                    "l.user_id AS uid, l.reasoning AS reason "
                    "ORDER BY ts DESC LIMIT $limit",
                    limit=limit
                )
            logs = []
            for record in result:
                logs.append({
                    "timestamp": record["ts"],
                    "operation": record["op"],
                    "target_id": record["tid"],
                    "user_id": record["uid"],
                    "reasoning": record["reason"],
                })
            return {"operations": logs, "count": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: Verify**

```bash
cd /home/zh/ai-study/backend && python3 -c "from app.api.v1.routes.kg_health import router; print('kg_health router OK')"
```

- [ ] **Step 3: Commit**

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| log_operation in Neo4jWriter | Task 1 |
| ContradictionDetector | Task 2 |
| KGLinter health check | Task 3 |
| Integrate into lead_agent (fuse_node前) | Task 4 |
| Lint API endpoint | Task 5 |

All requirements covered. No placeholders found. Types consistent across tasks.

---

**Plan complete.**