from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()


class ConflictDetail(BaseModel):
    id: int
    conflict_type: str
    severity: float
    entity_ids: List[int]
    statement_a: str
    statement_b: str
    status: str
    created_at: datetime


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


MOCK_CONFLICTS = {
    1: ConflictDetail(
        id=1,
        conflict_type="entity_conflict",
        severity=0.8,
        entity_ids=[101, 102],
        statement_a="知识点A是知识点B的父节点",
        statement_b="知识点A和知识点B是兄弟关系",
        status="pending",
        created_at=datetime(2026, 5, 1, 10, 0, 0),
    ),
    2: ConflictDetail(
        id=2,
        conflict_type="property_conflict",
        severity=0.6,
        entity_ids=[103],
        statement_a="知识点的难度为困难",
        statement_b="知识点的难度为简单",
        status="resolved",
        created_at=datetime(2026, 4, 30, 14, 30, 0),
    ),
}


@router.get("/conflicts", response_model=ConflictListResponse)
async def get_conflict_queue(
    status: Optional[str] = Query(None, description="过滤条件：pending, resolved, rejected"),
    min_severity: float = Query(0.0, ge=0.0, le=1.0, description="最低严重程度"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: User = Depends(get_current_user),
):
    conflicts = [c for c in MOCK_CONFLICTS.values() if c.severity >= min_severity]
    if status:
        conflicts = [c for c in conflicts if c.status == status]
    total = len(conflicts)
    pending_count = len([c for c in MOCK_CONFLICTS.values() if c.status == "pending"])
    return ConflictListResponse(
        conflicts=conflicts[offset : offset + limit],
        total=total,
        pending_count=pending_count,
    )


@router.get("/conflicts/{conflict_id}", response_model=ConflictDetail)
async def get_conflict_detail(
    conflict_id: int = Path(..., description="冲突ID"),
    current_user: User = Depends(get_current_user),
):
    if conflict_id not in MOCK_CONFLICTS:
        raise HTTPException(status_code=404, detail="冲突不存在")
    return MOCK_CONFLICTS[conflict_id]


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: int = Path(..., description="冲突ID"),
    request: ResolveRequest = None,
    current_user: User = Depends(get_current_user),
):
    if conflict_id not in MOCK_CONFLICTS:
        raise HTTPException(status_code=404, detail="冲突不存在")
    valid_resolutions = {"accepted_a", "accepted_b", "merged", "rejected"}
    if request.resolution not in valid_resolutions:
        raise HTTPException(status_code=400, detail="无效的resolution值")
    MOCK_CONFLICTS[conflict_id].status = "resolved"
    return {"message": "冲突已解决", "conflict_id": conflict_id, "resolution": request.resolution}


@router.post("/reviews")
async def submit_review(
    request: ReviewRequest = None,
    current_user: User = Depends(get_current_user),
):
    valid_recommendations = {"accept_a", "accept_b", "merge", "reject"}
    if request.recommendation not in valid_recommendations:
        raise HTTPException(status_code=400, detail="无效的recommendation值")
    if request.confidence < 0 or request.confidence > 1:
        raise HTTPException(status_code=400, detail="confidence必须在0到1之间")
    return {
        "message": "评审提交成功",
        "conflict_id": request.conflict_id,
        "expert_id": request.expert_id,
        "recommendation": request.recommendation,
    }


@router.get("/stats", response_model=StatsResponse)
async def get_arbitration_stats(
    current_user: User = Depends(get_current_user),
):
    return StatsResponse(
        total_conflicts=2,
        pending=1,
        resolved=1,
        rejected=0,
        auto_resolved=0,
        avg_resolution_time_hours=24.5,
        consensus_rate=0.85,
    )