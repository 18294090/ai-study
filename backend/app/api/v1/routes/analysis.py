from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.question import Question

from app.core.auth import get_current_user
import networkx as nx
from typing import List

router = APIRouter()

async def get_related_questions(subject_id: int, db: AsyncSession) -> List[Question]:
    """获取相关题目"""
    query = select(Question).filter(Question.subject_id == subject_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/knowledge-map/{subject_id}")
async def get_knowledge_map(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """生成知识点关联图"""
    try:
        # 检查学科是否存在
        if not await check_subject_exists(subject_id, db):
            raise HTTPException(status_code=404, detail="Subject not found")

        # 构建知识点网络
        G = nx.Graph()
        
        # 获取所有知识点
        query = select(KnowledgePoint).filter(KnowledgePoint.subject_id == subject_id)
        result = await db.execute(query)
        knowledge_points = result.scalars().all()
        
        # 添加节点和边
        for kp in knowledge_points:
            G.add_node(kp.id, name=kp.name)
            
        # 分析知识点关联
        for q in await get_related_questions(subject_id, db):
            for kp1 in q.knowledge_points:
                for kp2 in q.knowledge_points:
                    if kp1.id != kp2.id:
                        G.add_edge(kp1.id, kp2.id)
        
        # 添加错误处理
        if not knowledge_points:
            return {"nodes": [], "edges": [], "message": "No knowledge points found"}
            
        return {
            "nodes": [{"id": n, "name": G.nodes[n]["name"]} for n in G.nodes()],
            "edges": [{"source": u, "target": v} for u, v in G.edges()]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/error-patterns/{subject_id}")
async def analyze_error_patterns(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """分析错题模式"""
    try:
        # 检查学科是否存在
        if not await check_subject_exists(subject_id, db):
            raise HTTPException(status_code=404, detail="Subject not found")

        # 获取知识点错误频率
        knowledge_point_errors = await db.execute(
            select(
                KnowledgePoint.name,
                func.count(Question.id).label('error_count')
            ).join(Question)
            .filter(
                Question.subject_id == subject_id,
                Question.creator_id == current_user.id
            )
            .group_by(KnowledgePoint.id, KnowledgePoint.name)
            .order_by(func.count(Question.id).desc())
        )
        
        # 获取难度分布
        difficulty_distribution = await db.execute(
            select(
                Question.difficulty,
                func.count(Question.id).label('count')
            ).filter(Question.subject_id == subject_id)
            .group_by(Question.difficulty)
        )
        
        return {
            "knowledge_point_errors": dict(knowledge_point_errors),
            "difficulty_distribution": dict(difficulty_distribution),
            "total_questions": await get_total_questions(subject_id, db)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def check_subject_exists(subject_id: int, db: AsyncSession) -> bool:
    """检查学科是否存在"""
    from app.models.subject import Subject
    query = select(Subject).filter(Subject.id == subject_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

async def get_total_questions(subject_id: int, db: AsyncSession) -> int:
    """获取题目总数"""
    return await db.scalar(
        select(func.count(Question.id))
        .filter(Question.subject_id == subject_id)
    )
