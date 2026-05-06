from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.study_group import StudyGroup, StudyGroupMember

router = APIRouter(tags=["study-groups"])


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    member_count: int
    is_public: str
    created_at: datetime

    class Config:
        from_attributes = True


class MemberResponse(BaseModel):
    user_id: int
    nickname: Optional[str]
    role: str
    joined_at: datetime


class CreateGroupRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class GroupSearchResponse(BaseModel):
    groups: List[GroupResponse]
    total: int
    suggestions: Optional[List[str]] = None


@router.post("/", response_model=GroupResponse)
async def create_group(
    request: CreateGroupRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建学习小组 (AI 可辅助命名和描述)"""
    group = StudyGroup(
        name=request.name,
        description=request.description,
        owner_id=current_user.id,
        tags=request.tags,
        is_public="public"
    )
    db.add(group)

    await db.flush()

    member = StudyGroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="owner"
    )
    db.add(member)
    await db.commit()
    await db.refresh(group)

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        owner_id=group.owner_id,
        member_count=1,
        is_public=group.is_public,
        created_at=group.created_at
    )


@router.get("/", response_model=List[GroupResponse])
async def list_groups(
    is_public: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """列出学习小组"""
    stmt = select(StudyGroup)
    if is_public:
        stmt = stmt.filter(StudyGroup.is_public == is_public)
    if search:
        stmt = stmt.filter(StudyGroup.name.contains(search))
    stmt = stmt.order_by(StudyGroup.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    groups = result.scalars().all()

    responses = []
    for g in groups:
        count_result = await db.execute(
            select(func.count(StudyGroupMember.id)).filter(StudyGroupMember.group_id == g.id)
        )
        member_count = count_result.scalar() or 0
        responses.append(GroupResponse(
            id=g.id, name=g.name, description=g.description,
            owner_id=g.owner_id, member_count=member_count,
            is_public=g.is_public, created_at=g.created_at
        ))
    return responses


@router.get("/search")
async def search_groups(
    q: str = Query(..., min_length=1),
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """AI 搜索和推荐学习小组"""
    try:
        from app.services.group_advisor import search_groups_with_ai
        return await search_groups_with_ai(q, limit, db)
    except Exception:
        stmt = select(StudyGroup).filter(StudyGroup.name.contains(q)).limit(limit)
        result = await db.execute(stmt)
        groups = result.scalars().all()
        return {"groups": [{"id": g.id, "name": g.name} for g in groups], "suggestions": []}


@router.get("/recommendations")
async def get_group_recommendations(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """AI 为用户推荐适合的学习小组"""
    try:
        from app.services.group_advisor import recommend_groups_for_user
        return await recommend_groups_for_user(user_id, db)
    except Exception as e:
        return {"recommendations": [], "error": str(e)}


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取小组详情"""
    result = await db.execute(select(StudyGroup).filter(StudyGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    count_result = await db.execute(
        select(func.count(StudyGroupMember.id)).filter(StudyGroupMember.group_id == group_id)
    )
    member_count = count_result.scalar() or 0

    return GroupResponse(
        id=group.id, name=group.name, description=group.description,
        owner_id=group.owner_id, member_count=member_count,
        is_public=group.is_public, created_at=group.created_at
    )


@router.post("/{group_id}/join")
async def join_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """加入学习小组"""
    result = await db.execute(select(StudyGroup).filter(StudyGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    existing = await db.execute(
        select(StudyGroupMember).filter(
            StudyGroupMember.group_id == group_id,
            StudyGroupMember.user_id == current_user.id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already in group")

    member = StudyGroupMember(
        group_id=group_id,
        user_id=current_user.id,
        role="member"
    )
    db.add(member)
    await db.commit()

    return {"message": "Joined group", "group_id": group_id}


@router.get("/{group_id}/members")
async def list_members(
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    """列出小组成员"""
    result = await db.execute(
        select(StudyGroupMember).filter(StudyGroupMember.group_id == group_id)
    )
    members = result.scalars().all()
    return [
        MemberResponse(
            user_id=m.user_id,
            nickname=m.nickname,
            role=m.role,
            joined_at=m.joined_at
        )
        for m in members
    ]


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移除成员 (仅小组创建者可操作)"""
    result = await db.execute(select(StudyGroup).filter(StudyGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can remove members")

    result = await db.execute(
        select(StudyGroupMember).filter(
            StudyGroupMember.group_id == group_id,
            StudyGroupMember.user_id == user_id
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.delete(member)
    await db.commit()
    return {"message": "Member removed"}


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除小组 (仅创建者可操作)"""
    result = await db.execute(select(StudyGroup).filter(StudyGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only owner can delete group")

    await db.delete(group)
    await db.commit()
    return {"message": "Group deleted"}


@router.get("/{group_id}/suggestions")
async def get_group_suggestions(
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    """AI 为小组生成改进建议"""
    try:
        from app.services.group_advisor import suggest_group_improvements
        return await suggest_group_improvements(group_id, db)
    except Exception as e:
        return {"suggestions": [], "error": str(e)}