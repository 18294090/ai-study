from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.expert_reviewer import KGConflict, ExpertReview, ConflictQueue, ConflictType, ConflictStatus, RecommendationType
from app.services.expert_reviewer_service import ConflictDetector, ConflictResolver, ConsensusEngine, ConflictEvidence, KGConflict as ServiceConflict, ExpertReview as ServiceReview, ConsensusResult

router = APIRouter(prefix="/expert-reviewer", tags=["expert-reviewer"])


class ConflictDetail(BaseModel):
    id: int
    conflict_type: str
    severity: float
    entity_ids: List[int]
    statement_a: str
    statement_b: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConflictListResponse(BaseModel):
    conflicts: List[ConflictDetail]
    total: int
    pending_count: int


class ResolveRequest(BaseModel):
    resolution: str = Field(..., description="accepted_a | accepted_b | merged | rejected")
    reasoning: str
    resolver_id: int


class ReviewRequest(BaseModel):
    conflict_id: int
    expert_id: int
    recommendation: str = Field(..., description="accept_a | accept_b | merge | reject")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class StatsResponse(BaseModel):
    total_conflicts: int
    pending: int
    resolved: int
    rejected: int
    auto_resolved: int
    avg_resolution_time_hours: float
    consensus_rate: float


detector = ConflictDetector()
resolver = ConflictResolver()
consensus_engine = ConsensusEngine()


@router.get("/conflicts", response_model=ConflictListResponse)
async def get_conflict_queue(
    status: Optional[str] = Query(None, description="过滤条件：pending, resolved, rejected"),
    min_severity: float = Query(0.0, ge=0.0, le=1.0, description="最低严重程度"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(KGConflict)

    if status:
        stmt = stmt.filter(KGConflict.status == status)
    if min_severity > 0:
        stmt = stmt.filter(KGConflict.severity >= min_severity)

    stmt = stmt.order_by(KGConflict.severity.desc(), KGConflict.created_at.desc())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    conflicts = result.scalars().all()

    count_stmt = select(func.count(KGConflict.id))
    if status:
        count_stmt = count_stmt.filter(KGConflict.status == status)
    if min_severity > 0:
        count_stmt = count_stmt.filter(KGConflict.severity >= min_severity)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    pending_stmt = select(func.count(KGConflict.id)).filter(KGConflict.status == "pending")
    pending_result = await db.execute(pending_stmt)
    pending_count = pending_result.scalar() or 0

    conflict_details = []
    for c in conflicts:
        raw_entity_ids = c.entity_ids
        if isinstance(raw_entity_ids, str):
            try:
                entity_ids = json.loads(raw_entity_ids)
            except:
                entity_ids = []
        elif isinstance(raw_entity_ids, list):
            entity_ids = raw_entity_ids
        else:
            entity_ids = []
        conflict_details.append(ConflictDetail(
            id=c.id,
            conflict_type=c.conflict_type,
            severity=c.severity,
            entity_ids=entity_ids,
            statement_a=c.statement_a,
            statement_b=c.statement_b,
            status=c.status,
            created_at=c.created_at
        ))

    return ConflictListResponse(
        conflicts=conflict_details,
        total=total,
        pending_count=pending_count
    )


@router.get("/conflicts/{conflict_id}", response_model=ConflictDetail)
async def get_conflict_detail(
    conflict_id: int = Path(..., description="冲突ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(KGConflict).filter(KGConflict.id == conflict_id)
    )
    conflict = result.scalar_one_or_none()

    if not conflict:
        raise HTTPException(status_code=404, detail="冲突不存在")

    raw_entity_ids = conflict.entity_ids
    if isinstance(raw_entity_ids, str):
        try:
            entity_ids = json.loads(raw_entity_ids)
        except:
            entity_ids = []
    elif isinstance(raw_entity_ids, list):
        entity_ids = raw_entity_ids
    else:
        entity_ids = []

    return ConflictDetail(
        id=conflict.id,
        conflict_type=conflict.conflict_type,
        severity=conflict.severity,
        entity_ids=entity_ids,
        statement_a=conflict.statement_a,
        statement_b=conflict.statement_b,
        status=conflict.status,
        created_at=conflict.created_at
    )


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: int = Path(..., description="冲突ID"),
    request: Optional[ResolveRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(KGConflict).filter(KGConflict.id == conflict_id)
    )
    conflict = result.scalar_one_or_none()

    if not conflict:
        raise HTTPException(status_code=404, detail="冲突不存在")

    valid_resolutions = {"accepted_a", "accepted_b", "merged", "rejected"}
    if request and request.resolution not in valid_resolutions:
        raise HTTPException(status_code=400, detail="无效的resolution值")

    conflict.status = ConflictStatus.RESOLVED.value
    conflict.resolved_at = datetime.utcnow()
    conflict.resolution = request.resolution if request else "unknown"
    conflict.resolver_id = request.resolver_id if request else None

    await db.commit()

    return {"message": "冲突已解决", "conflict_id": conflict_id, "resolution": request.resolution if request else "unknown"}


@router.post("/reviews")
async def submit_review(
    request: Optional[ReviewRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request:
        raise HTTPException(status_code=400, detail="Request body required")

    valid_recommendations = {"accept_a", "accept_b", "merge", "reject"}
    if request.recommendation not in valid_recommendations:
        raise HTTPException(status_code=400, detail="无效的recommendation值")

    if request.confidence < 0 or request.confidence > 1:
        raise HTTPException(status_code=400, detail="confidence必须在0到1之间")

    conflict_result = await db.execute(
        select(KGConflict).filter(KGConflict.id == request.conflict_id)
    )
    conflict = conflict_result.scalar_one_or_none()
    if not conflict:
        raise HTTPException(status_code=404, detail="冲突不存在")

    review = ExpertReview(
        conflict_id=request.conflict_id,
        expert_id=request.expert_id,
        recommendation=request.recommendation,
        confidence=request.confidence,
        reasoning=request.reasoning,
        voted_at=datetime.utcnow()
    )
    db.add(review)

    conflict.status = ConflictStatus.REVIEWING.value
    await db.commit()

    return {
        "message": "评审提交成功",
        "conflict_id": request.conflict_id,
        "expert_id": request.expert_id,
        "recommendation": request.recommendation,
    }


@router.get("/stats", response_model=StatsResponse)
async def get_arbitration_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_result = await db.execute(select(func.count(KGConflict.id)))
    total_conflicts = total_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(KGConflict.id)).filter(KGConflict.status == "pending")
    )
    pending = pending_result.scalar() or 0

    resolved_result = await db.execute(
        select(func.count(KGConflict.id)).filter(KGConflict.status == "resolved")
    )
    resolved = resolved_result.scalar() or 0

    rejected_result = await db.execute(
        select(func.count(KGConflict.id)).filter(KGConflict.status == "rejected")
    )
    rejected = rejected_result.scalar() or 0

    auto_resolved_count = 0
    resolved_conflicts_result = await db.execute(
        select(KGConflict).filter(KGConflict.status == "resolved")
    )
    resolved_conflicts = resolved_conflicts_result.scalars().all()
    for c in resolved_conflicts:
        if c.resolution in ("accepted_a", "accepted_b", "merged"):
            auto_resolved_count += 1

    avg_time = 24.0
    if resolved > 0 and resolved_conflicts:
        total_time = sum(
            (c.resolved_at - c.created_at).total_seconds() / 3600
            for c in resolved_conflicts if c.resolved_at
        )
        avg_time = total_time / len(resolved_conflicts) if resolved_conflicts else 24.0

    consensus_rate = 0.85
    if resolved > 0:
        reviews_stmt = select(ExpertReview)
        reviews_result = await db.execute(reviews_stmt)
        reviews = reviews_result.scalars().all()
        if reviews:
            recommendation_counts = {}
            for r in reviews:
                recommendation_counts[r.recommendation] = recommendation_counts.get(r.recommendation, 0) + 1
            max_count = max(recommendation_counts.values()) if recommendation_counts else 0
            consensus_rate = max_count / len(reviews) if len(reviews) > 0 else 0.0

    return StatsResponse(
        total_conflicts=total_conflicts,
        pending=pending,
        resolved=resolved,
        rejected=rejected,
        auto_resolved=auto_resolved_count,
        avg_resolution_time_hours=avg_time,
        consensus_rate=consensus_rate
    )


@router.post("/conflicts/detect")
async def detect_conflicts(
    entity_ids: List[int],
    statement_a: str,
    statement_b: str,
    source_a: str = "",
    source_b: str = "",
    confidence_a: float = 0.8,
    confidence_b: float = 0.8,
    context_a: Optional[dict] = None,
    context_b: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = ConflictEvidence(
        entity_ids=entity_ids,
        statement_a=statement_a,
        statement_b=statement_b,
        source_a=source_a,
        source_b=source_b,
        confidence_a=confidence_a,
        confidence_b=confidence_b,
        context_a=context_a or {},
        context_b=context_b or {}
    )

    severity = detector.compute_severity(evidence)
    should_escalate = detector.should_escalate(severity)

    conflict_type = "contradiction"
    if context_a and context_b:
        if context_a.get("timestamp") and context_b.get("timestamp"):
            conflict_type = "temporal"

    conflict = KGConflict(
        conflict_type=conflict_type,
        severity=severity,
        entity_ids=entity_ids,
        statement_a=statement_a,
        statement_b=statement_b,
        source_a=source_a,
        source_b=source_b,
        context=context_a or {},
        status="pending" if should_escalate else "resolved",
        created_at=datetime.utcnow()
    )

    if not should_escalate:
        service_conflict = ServiceConflict(
            entity_id=entity_ids[0] if entity_ids else 0,
            evidence=evidence,
            severity=severity,
            requires_human_review=False
        )
        resolution = resolver.try_auto_resolve(service_conflict)
        if resolution:
            conflict.resolution = resolution.winner

    db.add(conflict)
    await db.commit()
    await db.refresh(conflict)

    return {
        "conflict_id": conflict.id,
        "severity": severity,
        "requires_human_review": should_escalate,
        "auto_resolved": not should_escalate
    }