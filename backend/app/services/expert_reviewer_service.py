from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ConflictEvidence:
    entity_ids: List[int]
    statement_a: str
    statement_b: str
    source_a: str
    source_b: str
    confidence_a: float
    confidence_b: float
    context_a: dict
    context_b: dict


@dataclass
class Resolution:
    winner: str
    confidence: float
    reasoning: str
    auto_resolved: bool


@dataclass
class KGConflict:
    entity_id: int
    evidence: ConflictEvidence
    severity: float = 0.0
    requires_human_review: bool = False


@dataclass
class ExpertReview:
    reviewer_id: str
    entity_id: int
    recommendation: str
    confidence: float
    reasoning: str


@dataclass
class ConsensusResult:
    recommendation: str
    agreement_score: float
    confidence: float


class ConflictDetector:
    def compute_severity(self, evidence: ConflictEvidence) -> float:
        entity_importance = min(1.0, len(evidence.entity_ids) * 0.2)
        source_reliability_diff = abs(evidence.confidence_a - evidence.confidence_b)
        confidence_diff = abs(evidence.confidence_a - evidence.confidence_b)
        context_coverage = min(1.0, (len(evidence.context_a) + len(evidence.context_b)) * 0.1)

        severity = (
            0.3 * entity_importance +
            0.3 * source_reliability_diff +
            0.2 * confidence_diff +
            0.2 * context_coverage
        )
        return max(0.0, min(1.0, severity))

    def detect_conflicts(self, entity_id: int, new_statement: str) -> List[KGConflict]:
        return []

    def should_escalate(self, severity: float) -> bool:
        return severity >= 0.5


class ConflictResolver:
    RULES = [
        "source_reliability",
        "temporal_precedence",
        "granularity_hierarchy",
    ]

    def try_auto_resolve(self, conflict: KGConflict) -> Optional[Resolution]:
        resolved = self.resolve_by_reliability(conflict)
        if resolved is None:
            resolved = self.resolve_by_recency(conflict)
        return resolved

    def resolve_by_reliability(self, conflict: KGConflict) -> Optional[Resolution]:
        evidence = conflict.evidence
        if evidence.confidence_a > evidence.confidence_b:
            return Resolution(
                winner="a",
                confidence=evidence.confidence_a,
                reasoning="Source A has higher reliability",
                auto_resolved=True,
            )
        elif evidence.confidence_b > evidence.confidence_a:
            return Resolution(
                winner="b",
                confidence=evidence.confidence_b,
                reasoning="Source B has higher reliability",
                auto_resolved=True,
            )
        return None

    def resolve_by_recency(self, conflict: KGConflict) -> Optional[Resolution]:
        context_a = conflict.evidence.context_a
        context_b = conflict.evidence.context_b
        timestamp_a = context_a.get("timestamp", 0)
        timestamp_b = context_b.get("timestamp", 0)

        if timestamp_a > timestamp_b:
            return Resolution(
                winner="a",
                confidence=conflict.evidence.confidence_a,
                reasoning="Statement A is more recent",
                auto_resolved=True,
            )
        elif timestamp_b > timestamp_a:
            return Resolution(
                winner="b",
                confidence=conflict.evidence.confidence_b,
                reasoning="Statement B is more recent",
                auto_resolved=True,
            )
        return None


class ConsensusEngine:
    def compute_consensus(self, reviews: List[ExpertReview]) -> ConsensusResult:
        if not reviews:
            return ConsensusResult(
                recommendation="no_review",
                agreement_score=0.0,
                confidence=0.0,
            )

        recommendation_counts: Dict[str, int] = {}
        total_confidence = 0.0

        for review in reviews:
            recommendation_counts[review.recommendation] = recommendation_counts.get(review.recommendation, 0) + 1
            total_confidence += review.confidence

        max_count = max(recommendation_counts.values())
        winners = [rec for rec, count in recommendation_counts.items() if count == max_count]
        recommendation = winners[0] if len(winners) == 1 else "mixed"
        agreement_score = max_count / len(reviews)
        confidence = total_confidence / len(reviews)

        return ConsensusResult(
            recommendation=recommendation,
            agreement_score=agreement_score,
            confidence=confidence,
        )
