"""AI-powered group advisor for search, recommendations, and suggestions."""

from typing import Dict, List, Any
import json

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_group import StudyGroup, StudyGroupMember
from app.models.subject import Subject
from app.models.user import User
from app.kg.src.llm_router import LLMRouter


async def search_groups_with_ai(query: str, limit: int, db: AsyncSession) -> Dict[str, Any]:
    """Search groups with AI assistance.

    Args:
        query: Search query string
        limit: Maximum number of results
        db: Database session

    Returns:
        Dictionary with groups and AI suggestions
    """
    stmt = select(StudyGroup).filter(StudyGroup.name.contains(query)).limit(limit * 2)
    result = await db.execute(stmt)
    groups = result.scalars().all()

    group_summaries = [
        {"id": g.id, "name": g.name, "description": g.description or "", "member_count": 0}
        for g in groups[:limit]
    ]

    prompt = f"""作为学习小组搜索助手，根据用户查询推荐合适的小组。

用户查询: {query}

候选小组:
{json.dumps(group_summaries, ensure_ascii=False, indent=2)}

请以JSON格式返回:
{{
    "recommended_ids": [小组ID列表，按相关度排序],
    "suggestions": ["如果候选不足，给出创建新小组的建议"],
    "reasoning": "推荐理由"
}}

只返回一个JSON对象。"""

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        result_data = json.loads(content.strip())

        recommended = [
            next((g for g in groups if g.id == gid), None)
            for gid in result_data.get("recommended_ids", [])
            if any(g.id == gid for g in groups)
        ]

        return {
            "groups": [
                {"id": g.id, "name": g.name, "description": g.description}
                for g in recommended[:limit]
            ],
            "suggestions": result_data.get("suggestions", []),
            "reasoning": result_data.get("reasoning", "")
        }

    except Exception as e:
        return {
            "groups": [{"id": g.id, "name": g.name} for g in groups[:limit]],
            "suggestions": [],
            "error": str(e)
        }


async def recommend_groups_for_user(user_id: int, db: AsyncSession) -> Dict[str, Any]:
    """Recommend groups for a user based on their profile and activity.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        Dictionary with recommended groups and reasoning
    """
    user = await db.get(User, user_id)
    if not user:
        return {"recommendations": [], "error": "User not found"}

    user_groups_query = select(StudyGroupMember.group_id).filter(
        StudyGroupMember.user_id == user_id
    )
    user_groups_result = await db.execute(user_groups_query)
    user_group_ids = [g for g in user_groups_result.scalars().all()]

    all_groups_query = select(StudyGroup).filter(
        StudyGroup.is_public == "public"
    )
    if user_group_ids:
        all_groups_query = all_groups_query.filter(~StudyGroup.id.in_(user_group_ids))
    all_groups_query = all_groups_query.limit(20)
    all_groups_result = await db.execute(all_groups_query)
    available_groups = all_groups_result.scalars().all()

    group_summaries = []
    for g in available_groups:
        count_result = await db.execute(
            select(func.count(StudyGroupMember.id)).filter(
                StudyGroupMember.group_id == g.id
            )
        )
        member_count = count_result.scalar() or 0
        group_summaries.append({
            "id": g.id,
            "name": g.name,
            "description": g.description or "",
            "tags": g.tags or [],
            "member_count": member_count
        })

    user_subjects = getattr(user, 'subjects', []) or []
    subject_names = [s.name if hasattr(s, 'name') else str(s) for s in user_subjects]

    prompt = f"""作为学习小组推荐助手，为用户推荐合适的小组。

用户: {user.username or user.email}
已加入小组数: {len(user_group_ids)}
学科兴趣: {', '.join(subject_names) or '未指定'}

可用小组:
{json.dumps(group_summaries, ensure_ascii=False, indent=2)}

请以JSON格式返回:
{{
    "recommended_ids": [推荐的小组ID列表],
    "reasoning": "推荐理由"
}}

只返回一个JSON对象。"""

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        result_data = json.loads(content.strip())

        recommended = [
            next((g for g in available_groups if g.id == gid), None)
            for gid in result_data.get("recommended_ids", [])
            if any(g.id == gid for g in available_groups)
        ]

        return {
            "recommendations": [
                {
                    "id": g.id,
                    "name": g.name,
                    "description": g.description,
                    "tags": g.tags
                }
                for g in recommended[:5]
            ],
            "reasoning": result_data.get("reasoning", "")
        }

    except Exception as e:
        return {
            "recommendations": [],
            "error": str(e)
        }


async def suggest_group_improvements(group_id: int, db: AsyncSession) -> Dict[str, Any]:
    """Suggest improvements for a group based on its members and activity.

    Args:
        group_id: Group ID
        db: Database session

    Returns:
        Dictionary with suggestions and reasoning
    """
    group = await db.get(StudyGroup, group_id)
    if not group:
        return {"suggestions": [], "error": "Group not found"}

    members_result = await db.execute(
        select(StudyGroupMember).filter(StudyGroupMember.group_id == group_id)
    )
    members = members_result.scalars().all()

    count_result = await db.execute(
        select(func.count(StudyGroupMember.id)).filter(
            StudyGroupMember.group_id == group_id
        )
    )
    member_count = count_result.scalar() or 0

    prompt = f"""作为学习小组顾问，分析小组并给出改进建议。

小组信息:
- 名称: {group.name}
- 描述: {group.description or '未填写'}
- 成员数: {member_count}
- 标签: {', '.join(group.tags or [])}
- 可见性: {group.is_public}

当前成员数: {len(members)}

请以JSON格式返回:
{{
    "suggestions": [
        "改进建议1",
        "改进建议2",
        ...
    ],
    "reasoning": "分析理由"
}}

只返回一个JSON对象。"""

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        result_data = json.loads(content.strip())
        return result_data

    except Exception as e:
        return {
            "suggestions": [],
            "error": str(e)
        }