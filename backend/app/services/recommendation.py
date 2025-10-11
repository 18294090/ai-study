from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.question import Question
from app.models.knowledge_point import KnowledgePoint
import numpy as np

class RecommendationService:
    async def get_recommended_questions(
        self,
        user_id: int,
        subject_id: int,
        db: AsyncSession,
        limit: int = 10
    ) -> List[Question]:
        """基于用户学习情况推荐题目"""
        # 获取用户答题历史
        user_history = await self._get_user_history(user_id, subject_id, db)
        # 分析薄弱知识点
        weak_points = self._analyze_weak_points(user_history)
        # 获取推荐题目
        recommended = await self._get_questions_by_knowledge_points(
            weak_points,
            user_history,
            db,
            limit
        )
        return recommended

    async def _get_questions_by_knowledge_points(
        self,
        knowledge_points: List[int],
        user_history: Dict,
        db: AsyncSession,
        limit: int
    ) -> List[Question]:
        """根据知识点获取推荐题目"""
        # 实现题目筛选逻辑
        query = select(Question).filter(
            Question.knowledge_point_id.in_(knowledge_points),
            Question.id.notin_(user_history['answered_questions'])
        ).order_by(Question.difficulty)
        result = await db.execute(query)
        return result.scalars().all()[:limit]

    async def generate_learning_path(
        self,
        user_id: int,
        subject_id: int,
        db: AsyncSession
    ) -> Dict:
        """生成个性化学习路径"""
        # 获取用户当前水平
        user_level = await self._get_user_level(user_id, subject_id, db)
        # 获取知识点依赖关系
        knowledge_graph = await self._build_knowledge_graph(subject_id, db)
        
        # 生成最优学习路径
        path = self._optimize_learning_path(knowledge_graph, user_level)
        return {
            "path": path,
            "estimated_time": self._calculate_study_time(path),
            "milestones": self._generate_milestones(path)
        }

    async def adjust_difficulty(
        self,
        user_id: int,
        subject_id: int,
        current_performance: float,
        db: AsyncSession
    ) -> int:
        """动态调整推荐题目难度"""
        # 分析最近表现
        performance_trend = await self._analyze_performance_trend(
            user_id,
            subject_id,
            db
        )
        
        # 计算新的推荐难度
        new_difficulty = self._calculate_optimal_difficulty(
            current_performance,
            performance_trend
        )
        return new_difficulty

    def _calculate_optimal_difficulty(
        self,
        current_performance: float,
        performance_trend: List[float]
    ) -> int:
        """计算最优难度"""
        if not performance_trend:
            return 3  # 默认中等难度
            
        avg_performance = np.mean(performance_trend)
        if avg_performance > 0.8:  # 表现优秀，提高难度
            return min(5, int(current_performance + 1))
        elif avg_performance < 0.6:  # 表现欠佳，降低难度
            return max(1, int(current_performance - 1))
        return int(current_performance)  # 保持当前难度
