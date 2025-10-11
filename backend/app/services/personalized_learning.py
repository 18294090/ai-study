from typing import List, Dict
import networkx as nx
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_point import KnowledgePoint
from app.models.user_progress import UserProgress

class PersonalizedLearningPath:
    async def generate_path(
        self,
        user_id: int,
        subject_id: int,
        db: AsyncSession
    ) -> Dict:
        # 构建知识图谱
        G = nx.DiGraph()
        
        # 获取用户当前掌握度
        user_progress = await self._get_user_progress(user_id, subject_id, db)
        
        # 获取知识点依赖关系
        knowledge_points = await self._get_knowledge_dependencies(subject_id, db)
        
        # 构建学习路径
        path = self._build_learning_path(knowledge_points, user_progress)
        
        return {
            "learning_path": path,
            "estimated_duration": self._calculate_duration(path),
            "prerequisites": self._get_prerequisites(path),
            "milestones": self._generate_milestones(path)
        }

    def _build_learning_path(self, knowledge_points: List, progress: Dict) -> List:
        """基于知识点依赖关系和用户进度构建最优学习路径"""
        return sorted(
            knowledge_points,
            key=lambda x: (
                self._calculate_priority(x, progress),
                -progress.get(x.id, 0)
            )
        )
