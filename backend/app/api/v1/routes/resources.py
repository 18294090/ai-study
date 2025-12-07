from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.db.session import get_db
from app.models.resource import Resource, ResourceType
from app.schemas.resource import ResourceCreate, ResourceUpdate, ResourceResponse
from app.core.auth import get_current_user
from app.models.user import User
from app.core.permissions import check_subject_member

router = APIRouter()

@router.post("/knowledge-points/{knowledge_point_id}/resources", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    resource: ResourceCreate,
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传资料（学科成员可上传）"""
    # 检查用户是否是知识点所属学科的成员
    # 首先获取知识点
    from app.models.knowledge import KnowledgePoint
    knowledge_point = await db.get(KnowledgePoint, knowledge_point_id)
    if not knowledge_point:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 检查用户是否是学科成员
    await check_subject_member(knowledge_point.subject_id, current_user, db)

    # 创建资源
    db_resource = Resource(
        **resource.dict(),
        knowledge_point_id=knowledge_point_id,
        user_id=current_user.id
    )
    db.add(db_resource)
    await db.commit()
    await db.refresh(db_resource)
    return db_resource

@router.get("/knowledge-points/{knowledge_point_id}/resources", response_model=List[ResourceResponse])
async def get_resources(
    knowledge_point_id: int = Path(..., description="知识点ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取知识点的所有资料（学科成员可查看）"""
    # 检查用户是否是知识点所属学科的成员
    from app.models.knowledge import KnowledgePoint
    knowledge_point = await db.get(KnowledgePoint, knowledge_point_id)
    if not knowledge_point:
        raise HTTPException(status_code=404, detail="知识点不存在")

    await check_subject_member(knowledge_point.subject_id, current_user, db)

    query = select(Resource).where(Resource.knowledge_point_id == knowledge_point_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/resources/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: int = Path(..., description="资源ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取资源详情（学科成员可查看）"""
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    # 检查用户是否是资源所属学科的成员
    await check_subject_member(resource.knowledge_point.subject_id, current_user, db)

    return resource

@router.put("/resources/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_update: ResourceUpdate,
    resource_id: int = Path(..., description="资源ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新资源（仅上传者可修改）"""
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    # 检查用户是否是资源所属学科的成员
    await check_subject_member(resource.knowledge_point.subject_id, current_user, db)

    # 只有上传者可以修改资源
    if resource.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有上传者才能修改此资源")

    # 更新资源
    for key, value in resource_update.dict(exclude_unset=True).items():
        setattr(resource, key, value)

    await db.commit()
    await db.refresh(resource)
    return resource

@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: int = Path(..., description="资源ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除资源（仅上传者可删除）"""
    resource = await db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")

    # 检查用户是否是资源所属学科的成员
    await check_subject_member(resource.knowledge_point.subject_id, current_user, db)

    # 只有上传者可以删除资源
    if resource.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有上传者才能删除此资源")

    await db.delete(resource)
    await db.commit()

@router.get("/subjects/{subject_id}/resources", response_model=List[ResourceResponse])
async def get_subject_resources(
    subject_id: int = Path(..., description="学科ID"),
    resource_type: Optional[ResourceType] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取学科的所有资料（学科成员可查看）"""
    # 检查用户是否是学科成员
    await check_subject_member(subject_id, current_user, db)

    # 查询学科下的所有资源
    from app.models.knowledge import KnowledgePoint
    query = select(Resource).join(
        KnowledgePoint, Resource.knowledge_point_id == KnowledgePoint.id
    ).where(KnowledgePoint.subject_id == subject_id)

    if resource_type:
        query = query.where(Resource.resource_type == resource_type)

    result = await db.execute(query)
    return result.scalars().all()