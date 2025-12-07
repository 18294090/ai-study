import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from typing import List
from app.db.neo4j_utils import (
    create_knowledge_point as sync_create_knowledge_point,
    get_knowledge_points_by_subject,
    get_session,
    get_knowledge_point as get_kp_by_id,
    create_typed_relation,
    search_knowledge_points,
)
from app.schemas.knowledge_point import KnowledgePointCreate, KnowledgePointUpdate, KnowledgePointResponse
from app.core.auth import get_current_user
from app.core.permissions import check_subject_member
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.knowledge_point import KnowledgePoint as SQLKnowledgePoint, DifficultyLevel
from app.utils.knowledge_point_identifiers import (
    generate_knowledge_point_code,
    generate_knowledge_point_slug,
)
from app.services.knowledge_point_validator import (
    validate_creation,
    validate_update,
)
from app.services.knowledge_point_audit import record_audit_event
from app.utils.simple_cache import cache_get, cache_set, cache_invalidate
from app.core.config import settings
from app.services.knowledge_point_service import (
    get_subtree as svc_get_subtree,
    get_ancestors as svc_get_ancestors,
    build_tree as svc_build_tree,
    move_knowledge_point as svc_move_kp,
    add_closure_for_insert,
)

router = APIRouter()

async def verify_subject_membership(subject_id: int, current_user: User, db: AsyncSession) -> None:
    """验证用户是否是学科成员（用于知识点管理）"""
    await check_subject_member(subject_id, current_user, db)

@router.post("/subjects/{subject_id}/knowledge-points", response_model=KnowledgePointResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_point_route(
    knowledge_point: KnowledgePointCreate,
    subject_id: int = Path(..., description="学科ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await verify_subject_membership(subject_id, current_user, db)
    # 校验：同一学科下名称唯一
    await validate_creation(db, subject_id, knowledge_point.name)
    difficulty_value = knowledge_point.difficulty or DifficultyLevel.MEDIUM.value
    kp_code = generate_knowledge_point_code(subject_id)
    kp_slug = generate_knowledge_point_slug(knowledge_point.name, subject_id)
    # 1) 先写关系型数据库，获取自增ID
    new_kp = SQLKnowledgePoint(
        code=kp_code,
        slug=kp_slug,
        name=knowledge_point.name,
        description=knowledge_point.description or "",
        subject_id=subject_id,
        difficulty=difficulty_value,
        grade_level=None,
        creator_id=current_user.id,
        created_by=str(current_user.username or current_user.id),
        updated_by=str(current_user.username or current_user.id),
        parent_id=knowledge_point.parent_id if hasattr(knowledge_point, "parent_id") else None,
    )
    db.add(new_kp)
    await db.commit()
    await db.refresh(new_kp)

    # 2) 同步到 Neo4j（异步执行同步函数）
    kp_data = await asyncio.get_event_loop().run_in_executor(
        None,
        sync_create_knowledge_point,
        new_kp.id,
        knowledge_point.name,
        knowledge_point.description,
        difficulty_value,
        subject_id,
        current_user.id,
        kp_code,
        kp_slug,
    )
    if not kp_data:
        raise HTTPException(status_code=500, detail="创建知识点失败(Neo4j)")
    # 2.5) 维护闭包表与 path/depth（仅关系型）
    try:
        await add_closure_for_insert(db, new_kp.id, new_kp.parent_id)
        await db.commit()
        await db.refresh(new_kp)
    except Exception:
        await db.rollback()
    # 记录审计日志（创建）
    try:
        await record_audit_event(
            db,
            new_kp,
            stage="create",
            reviewer_id=str(current_user.id),
            reviewer_name=str(current_user.username or current_user.id),
            status="pending",
            comment=None,
        )
        await db.commit()
    except Exception:
        # 审计失败不影响主流程
        await db.rollback()
    # 失效缓存
    cache_invalidate(f"kp:subject:{subject_id}:")
    return kp_data

@router.get("/subjects/{subject_id}/knowledge-points", response_model=List[KnowledgePointResponse])
async def get_knowledge_points_by_subject_route(
    subject_id: int = Path(..., description="学科ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await verify_subject_membership(subject_id, current_user, db)
    # 读取缓存
    cache_key = f"kp:subject:{subject_id}:list"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    kps = get_knowledge_points_by_subject(subject_id)
    # 写入缓存
    try:
        cache_set(cache_key, kps, settings.CACHE_TTL)
    except Exception:
        pass
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
    # 先查询 Neo4j 获取 subject_id 以便校验与缓存失效
    with get_session() as session:
        result_pre = session.run("MATCH (kp:KnowledgePoint {id: $id}) RETURN kp", id=knowledge_point_id)
        pre = result_pre.single()
        if not pre:
            raise HTTPException(status_code=404, detail="知识点不存在")
        pre_kp = pre["kp"]
        subject_id = pre_kp.get("subject_id") if hasattr(pre_kp, "get") else pre_kp["subject_id"]

    # 校验名称唯一（如有修改）
    update_data = knowledge_point_update.dict(exclude_unset=True)
    new_name = update_data.get("name")
    if new_name is not None:
        # 需要访问数据库会话，FastAPI 依赖未在签名里，这里简单新开一次获取（或改造签名）
        # 为保持最小改动，本路由仅做校验与缓存失效
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await validate_update(db, subject_id, new_name, knowledge_point_id)
            # 同步关键字段到关系型（若存在）
            obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
            if obj is not None:
                if "name" in update_data:
                    obj.name = update_data["name"]
                if "description" in update_data:
                    obj.description = update_data["description"]
                obj.updated_by = str(current_user.username or current_user.id)
                await db.commit()
                await db.refresh(obj)

    # 同步到 Neo4j
    with get_session() as session:
        set_clause = ", ".join([f"kp.{k} = ${k}" for k in update_data.keys()])
        result = session.run(
            f"MATCH (kp:KnowledgePoint {{id: $id}}) SET {set_clause} RETURN kp",
            id=knowledge_point_id,
            **update_data,
        )
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="知识点不存在")
        updated = record["kp"]

    # 审计记录（更新）
    try:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
            if obj is not None:
                await record_audit_event(
                    db,
                    obj,
                    stage="update",
                    reviewer_id=str(current_user.id),
                    reviewer_name=str(current_user.username or current_user.id),
                    status="pending",
                )
                await db.commit()
    except Exception:
        pass

    # 失效缓存
    cache_invalidate(f"kp:subject:{subject_id}:")
    return updated

# 删除知识点
@router.delete("/knowledge-points/{knowledge_point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_point(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 从 Neo4j 获取知识点
    kp = get_kp_by_id(knowledge_point_id)
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")    
    # 验证用户是否是该知识点所属学科的成员
    subject_id = kp["subject_id"] if hasattr(kp, '__getitem__') else getattr(kp, 'subject_id')
    await verify_subject_membership(subject_id, current_user, db)
    # 删除知识点：先删 Neo4j，再删关系型
    with get_session() as session:
        session.run("MATCH (kp:KnowledgePoint {id: $id}) DELETE kp", id=knowledge_point_id)
    # 删除关系型数据库记录（若存在）
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj:
        await db.delete(obj)
        await db.commit()
    # 失效缓存
    try:
        cache_invalidate(f"kp:subject:{subject_id}:")
    except Exception:
        pass
    return {"message": "知识点删除成功"}

@router.post("/knowledge-points/{id1}/relate/{id2}", status_code=status.HTTP_201_CREATED)
async def create_relation(
    id1: int = Path(..., description="知识点1 ID"),
    id2: int = Path(..., description="知识点2 ID"),
    strength: float = 1.0,
    rel_type: str = Query("RELATES_TO", description="关系类型，默认RELATES_TO"),
    current_user: User = Depends(get_current_user)
):
    # 验证知识点存在（可选）
    kp1 = get_kp_by_id(id1)
    kp2 = get_kp_by_id(id2)
    if not kp1 or not kp2:
        raise HTTPException(status_code=404, detail="知识点不存在")
    try:
        # 支持带类型的关系创建并做简单防环
        create_typed_relation(id1, id2, rel_type=rel_type, strength=strength)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 失效缓存（根据 kp1 所属学科）
    try:
        subject_id = kp1.get("subject_id") if hasattr(kp1, "get") else kp1["subject_id"]
        cache_invalidate(f"kp:subject:{subject_id}:")
    except Exception:
        pass
    return {"message": "关系创建成功", "type": rel_type}


@router.get("/knowledge-points/search", response_model=List[KnowledgePointResponse])
async def search_kps(
    subject_id: int = Query(..., description="学科ID"),
    q: str = Query("", description="搜索关键字(名称/描述)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_subject_membership(subject_id, current_user, db)
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


@router.get("/knowledge-points/{knowledge_point_id}/subtree")
async def get_kp_subtree(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 验证学科成员权限
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    await verify_subject_membership(obj.subject_id, current_user, db)
    return await svc_get_subtree(db, knowledge_point_id)


@router.get("/knowledge-points/{knowledge_point_id}/ancestors")
async def get_kp_ancestors(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    await verify_subject_membership(obj.subject_id, current_user, db)
    return await svc_get_ancestors(db, knowledge_point_id)


@router.get("/knowledge-points/{knowledge_point_id}/tree")
async def get_kp_tree(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    await verify_subject_membership(obj.subject_id, current_user, db)
    return await svc_build_tree(db, knowledge_point_id)


@router.post("/knowledge-points/{knowledge_point_id}/move")
async def move_kp(
    knowledge_point_id: int = Path(..., description="要移动的知识点ID"),
    new_parent_id: int | None = Query(None, description="新的父节点ID，可为空表示移动为根"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 加载当前节点
    obj = await db.get(SQLKnowledgePoint, knowledge_point_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="知识点不存在")
    # 权限：必须是所属学科成员
    await verify_subject_membership(obj.subject_id, current_user, db)
    # 若指定父节点，需同学科
    if new_parent_id is not None:
        parent = await db.get(SQLKnowledgePoint, new_parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="父知识点不存在")
        if parent.subject_id != obj.subject_id:
            raise HTTPException(status_code=400, detail="禁止跨学科移动知识点")

    # 执行移动
    try:
        moved = await svc_move_kp(db, knowledge_point_id, new_parent_id)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    if moved is None:
        raise HTTPException(status_code=500, detail="移动知识点失败")
    # 失效缓存
    cache_invalidate(f"kp:subject:{obj.subject_id}:")
    return {"id": moved.id, "parent_id": moved.parent_id, "path": moved.path, "depth": moved.depth}
