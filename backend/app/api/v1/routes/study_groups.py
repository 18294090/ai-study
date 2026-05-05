from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.study_group import StudyGroup, StudyGroupMember

router = APIRouter(prefix="/study-groups", tags=["study-groups"])


class CreateGroupRequest(BaseModel):
    name: str
    description: Optional[str] = None
    subject_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    is_public: str = "public"


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: int
    member_count: int
    is_public: str
    created_at: datetime


class MemberResponse(BaseModel):
    user_id: int
    nickname: Optional[str]
    role: str
    joined_at: datetime


class AddMemberRequest(BaseModel):
    user_id: int
    nickname: Optional[str] = None


@router.post("/", response_model=GroupResponse)
async def create_group(request: CreateGroupRequest, db: AsyncSession, current_user: User):
    """创建学习小组"""
    group = StudyGroup(
        name=request.name,
        description=request.description,
        owner_id=current_user.id,
        subject_ids=request.subject_ids,
        tags=request.tags,
        is_public=request.is_public
    )
    db.add(group)
    
    member = StudyGroupMember(
        group_id=0,
        user_id=current_user.id,
        role="owner"
    )
    
    await db.flush()
    member.group_id = group.id
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
    current_user: User = Depends(get_current_user)
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


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(group_id: int, db: AsyncSession, current_user: User):
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


@router.post("/{group_id}/members")
async def add_member(group_id: int, request: AddMemberRequest, db: AsyncSession, current_user: User):
    """添加成员到小组"""
    result = await db.execute(select(StudyGroup).filter(StudyGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    existing = await db.execute(
        select(StudyGroupMember).filter(
            StudyGroupMember.group_id == group_id,
            StudyGroupMember.user_id == request.user_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already in group")
    
    member = StudyGroupMember(
        group_id=group_id,
        user_id=request.user_id,
        role="member",
        nickname=request.nickname
    )
    db.add(member)
    await db.commit()
    
    return {"message": "Member added", "user_id": request.user_id}


@router.get("/{group_id}/members")
async def list_members(group_id: int, db: AsyncSession, current_user: User):
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
async def remove_member(group_id: int, user_id: int, db: AsyncSession, current_user: User):
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
    
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove owner")
    
    await db.delete(member)
    await db.commit()
    return {"message": "Member removed"}


@router.delete("/{group_id}")
async def delete_group(group_id: int, db: AsyncSession, current_user: User):
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