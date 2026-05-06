import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List
from app.db.neo4j_utils import (
    get_knowledge_points_by_subject,
    get_session,
    get_knowledge_point as get_kp_by_id,
    search_knowledge_points,
)
from app.schemas.knowledge_point import KnowledgePointResponse
from app.core.auth import get_current_user
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.knowledge_point import KnowledgePoint as SQLKnowledgePoint
from app.utils.simple_cache import cache_get, cache_set, cache_invalidate
from app.core.config import settings
from app.services.knowledge_point_service import (
    get_subtree as svc_get_subtree,
    get_ancestors as svc_get_ancestors,
    build_tree as svc_build_tree,
)

router = APIRouter()


@router.get("/{knowledge_point_id}", response_model=KnowledgePointResponse)
async def get_knowledge_point(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    current_user: User = Depends(get_current_user)
):
    """获取知识点详情（只读）"""
    with get_session() as session:
        result = session.run("MATCH (kp:KnowledgePoint {id: $id}) RETURN kp", id=knowledge_point_id)
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="知识点不存在")
        return record["kp"]


@router.get("/search", response_model=List[KnowledgePointResponse])
async def search_kps(
    subject_id: int = Query(..., description="学科ID"),
    q: str = Query("", description="搜索关键字(名称/描述)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索知识点（只读）"""
    key = f"kp:subject:{subject_id}:search:{(q or '').strip().lower()}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    data = search_knowledge_points(subject_id, q)
    try:
        cache_set(key, data, settings.CACHE_TTL)
    except Exception:
        pass
    return data


@router.get("/{knowledge_point_id}/subtree")
async def get_kp_subtree(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识点子树（只读）"""
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return await svc_get_subtree(db, knowledge_point_id)


@router.get("/{knowledge_point_id}/ancestors")
async def get_kp_ancestors(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识点祖先路径（只读）"""
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return await svc_get_ancestors(db, knowledge_point_id)


@router.get("/{knowledge_point_id}/tree")
async def get_kp_tree(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识点完整树结构（只读）"""
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return await svc_build_tree(db, knowledge_point_id)