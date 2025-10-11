from fastapi import APIRouter, Depends, HTTPException, status, Path
from typing import List, Optional
from app.db.neo4j_utils import create_knowledge_point, get_knowledge_points_by_subject, get_session, get_knowledge_point, create_knowledge_point_relation  # 修改此行
from app.schemas.knowledge_point import KnowledgePointCreate, KnowledgePointUpdate, KnowledgePointResponse
from app.core.auth import get_current_user
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.subject import Subject
from sqlalchemy import select
import asyncio
from app.db.neo4j_utils import create_knowledge_point as sync_create_knowledge_point

router = APIRouter()

async def verify_subject_ownership(subject_id: int, current_user: User, db: AsyncSession) -> Subject:
    query = select(Subject).filter(Subject.id == subject_id, Subject.user_id == current_user.id)
    result = await db.execute(query)
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学科不存在或您没有权限访问")
    return subject

@router.post("/subjects/{subject_id}/knowledge-points", response_model=KnowledgePointResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_point_route(
    knowledge_point: KnowledgePointCreate,  # 移到前面，无默认值
    subject_id: int = Path(..., description="学科ID"),  # 有默认值
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_subject_ownership(subject_id, current_user, db)
    # 异步运行同步 Neo4j 调用
    kp_data = await asyncio.get_event_loop().run_in_executor(None, sync_create_knowledge_point,
        knowledge_point.id, knowledge_point.name, knowledge_point.description,
        knowledge_point.difficulty, subject_id, current_user.id
    )
    if not kp_data:
        raise HTTPException(status_code=500, detail="创建知识点失败")
    return kp_data

@router.get("/subjects/{subject_id}/knowledge-points", response_model=List[KnowledgePointResponse])
async def get_knowledge_points_by_subject_route(
    subject_id: int = Path(..., description="学科ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_subject_ownership(subject_id, current_user, db)
    kps = get_knowledge_points_by_subject(subject_id)
    return kps

@router.get("/knowledge-points/{knowledge_point_id}", response_model=KnowledgePointResponse)
async def get_knowledge_point(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    current_user: User = Depends(get_current_user)
):
    with get_session() as session:
        result = session.run("MATCH (kp:KnowledgePoint {id: $id}) RETURN kp", id=knowledge_point_id)
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="知识点不存在")
        return record["kp"]

@router.put("/knowledge-points/{knowledge_point_id}", response_model=KnowledgePointResponse)
async def update_knowledge_point(
    knowledge_point_update: KnowledgePointUpdate,  # 移到前面，无默认值
    knowledge_point_id: int = Path(..., description="知识点ID"),  # 有默认值
    current_user: User = Depends(get_current_user)
):
    with get_session() as session:
        set_clause = ", ".join([f"kp.{k} = ${k}" for k in knowledge_point_update.dict(exclude_unset=True).keys()])
        result = session.run(f"MATCH (kp:KnowledgePoint {{id: $id}}) SET {set_clause} RETURN kp", id=knowledge_point_id, **knowledge_point_update.dict(exclude_unset=True))
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="知识点不存在")
        return record["kp"]

# 删除知识点
@router.delete("/knowledge-points/{knowledge_point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_point(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 从 Neo4j 获取知识点
    kp = get_knowledge_point(knowledge_point_id)
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")    
    # 验证用户是否拥有该知识点所属的学科
    await verify_subject_ownership(kp["subject_id"], current_user, db)    
    # 删除知识点
    with get_session() as session:
        session.run("MATCH (kp:KnowledgePoint {id: $id}) DELETE kp", id=knowledge_point_id)
    # 刷新知识点
    kp = get_knowledge_point(knowledge_point_id)
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return {"message": "知识点删除成功"}

@router.post("/knowledge-points/{id1}/relate/{id2}", status_code=status.HTTP_201_CREATED)
async def create_relation(
    id1: int = Path(..., description="知识点1 ID"),
    id2: int = Path(..., description="知识点2 ID"),
    strength: float = 1.0,
    current_user: User = Depends(get_current_user)
):
    # 验证知识点存在（可选）
    kp1 = get_knowledge_point(id1)
    kp2 = get_knowledge_point(id2)
    if not kp1 or not kp2:
        raise HTTPException(status_code=404, detail="知识点不存在")
    
    create_knowledge_point_relation(id1, id2, strength)
    return {"message": "关系创建成功"}
