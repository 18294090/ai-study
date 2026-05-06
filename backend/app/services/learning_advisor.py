"""AI-powered learning advisor for generating study suggestions."""

from typing import Dict, List, Any
import json

from app.models.subject import Subject
from app.models.knowledge import KnowledgePoint
from app.models.mastery import MasteryRecord
from app.kg.src.llm_router import LLMRouter


async def generate_subject_suggestions(
    subject_id: int,
    user_id: int,
    db
) -> Dict[str, Any]:
    """Generate AI-powered study suggestions for a subject.

    Args:
        subject_id: The subject ID
        user_id: The user ID
        db: Database session

    Returns:
        Dictionary with suggestions and reasoning
    """
    from sqlalchemy import select

    subject = await db.get(Subject, subject_id)
    if not subject:
        return {"suggestions": [], "error": "Subject not found"}

    kp_query = select(KnowledgePoint).where(KnowledgePoint.subject_id == subject_id)
    kp_result = await db.execute(kp_query)
    knowledge_points = kp_result.scalars().all()

    mastery_query = select(MasteryRecord).where(
        MasteryRecord.user_id == user_id,
        MasteryRecord.concept_id.in_([kp.id for kp in knowledge_points])
    )
    mastery_result = await db.execute(mastery_query)
    mastery_records = {m.concept_id: m for m in mastery_result.scalars().all()}

    weak_points = []
    for kp in knowledge_points:
        mastery = mastery_records.get(kp.id)
        if mastery and mastery.mastery_level < 0.6:
            weak_points.append({
                "id": kp.id,
                "name": kp.name,
                "mastery": mastery.mastery_level
            })

    prompt = f"""作为学习顾问，分析以下情况并给出学习建议。

学科: {subject.name} (学段: {subject.grade_level or '未指定'})
知识点总数: {len(knowledge_points)}
已掌握: {len([m for m in mastery_records.values() if m.mastery_level >= 0.6])}
薄弱知识点: {len(weak_points)}

薄弱知识点列表:
{json.dumps(weak_points[:10], ensure_ascii=False, indent=2)}

请以JSON格式返回学习建议:
{{
    "focus_areas": ["建议重点学习的知识点名称"],
    "learning_order": ["建议学习顺序"],
    "estimated_time": "预计学习时间",
    "reasoning": "给出建议的理由"
}}

只返回一个JSON对象。"""

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        suggestions = json.loads(content.strip())
        return suggestions

    except Exception as e:
        return {
            "suggestions": [],
            "error": f"LLM调用失败: {str(e)}",
            "weak_points": weak_points[:5]
        }