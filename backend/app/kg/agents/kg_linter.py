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
        if not textbook_id:
            return issues
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (s)-[r]->(o) WHERE r.textbook_id = $tid "
                    "RETURN s.id AS sid, o.id AS oid, r.predicate AS rel LIMIT 50",
                    tid=textbook_id
                )
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