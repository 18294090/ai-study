# backend/app/kg/agents/contradiction_detector.py
from __future__ import annotations
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from difflib import SequenceMatcher
from pydantic import BaseModel


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

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Return [0,1] similarity ratio using difflib as a lightweight semantic proxy.
        When FlagEmbedding is available this can be replaced with cosine similarity."""
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _check_entity_conflicts(self, triple: Any, textbook_id: str) -> List[Contradiction]:
        """Flag entity conflicts based on semantic similarity of descriptions.

        Threshold rationale:
          - similarity < 0.3  → descriptions are clearly different → potential conflict
          - 0.3 <= sim < 0.7  → ambiguous, route to human review
          - sim >= 0.7        → descriptions are consistent, no conflict
        """
        conflicts = []
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (e {id: $id}) WHERE e.textbook_id <> $textbook_id "
                    "RETURN e.id AS id, e.name AS name, e.description AS desc, e.textbook_id AS source",
                    id=triple.subject.id, textbook_id=textbook_id,
                )
                existing = result.data()
                if existing:
                    new_desc = triple.subject.description or ""
                    for e in existing:
                        old_desc = e["desc"] or ""
                        sim = self._text_similarity(new_desc, old_desc)
                        if sim < 0.3:
                            severity = 0.8
                            resolution = "flag_for_review"
                            label = "描述语义差异显著"
                        elif sim < 0.7:
                            severity = 0.5
                            resolution = "flag_for_review"
                            label = "描述部分不一致"
                        else:
                            continue  # consistent enough, skip
                        conflicts.append(Contradiction(
                            type="entity_conflict",
                            triple_a_id=triple.subject.id,
                            triple_b_id=e["id"],
                            severity=severity,
                            resolution=resolution,
                            description=(
                                f"实体 {triple.subject.name}：{label}（相似度={sim:.2f}，来源: {e['source']}）"
                            ),
                        ))
        except Exception:
            pass
        return conflicts

    def _check_relation_conflicts(self, triple: Any, textbook_id: str) -> List[Contradiction]:
        conflicts = []
        if triple.predicate.value not in ("is_a", "part_of", "requires", "causes"):
            return conflicts

        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                inverse_map = {
                    "is_a": "is_a",
                    "part_of": "contains",
                    "requires": "enables",
                    "causes": "result_of",
                }
                inverse_pred = inverse_map.get(triple.predicate.value)
                if inverse_pred:
                    result = session.run(
                    "MATCH (s)-[r]->(o) WHERE s.id = $sid AND o.id = $oid AND type(r) = $inverse "
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

    def resolve(self, contradiction: Contradiction) -> str:
        if contradiction.severity < 0.5:
            return contradiction.resolution
        return "flag_for_review"