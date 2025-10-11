from typing import List, Dict
import numpy as np
from sqlalchemy import select
from app.models.question import Question
from app.models.knowledge_point import KnowledgePoint

class PaperGenerator:
    def __init__(self):
        self.difficulty_weights = {
            1: 0.1,  # 简单题
            2: 0.2,  # 较简单题
            3: 0.4,  # 中等难度
            4: 0.2,  # 较难题
            5: 0.1   # 难题
        }
    
    async def generate_paper(
        self,
        subject_id: int,
        total_score: int,
        question_count: int,
        db: AsyncSession
    ) -> List[Question]:
        """智能生成试卷"""
        # 获取知识点覆盖
        knowledge_points = await self._get_knowledge_points(subject_id, db)
        
        # 计算每个难度等级的题目数量
        difficulty_distribution = self._calculate_difficulty_distribution(
            question_count,
            self.difficulty_weights
        )
        
        # 选择题目
        selected_questions = []
        for difficulty, count in difficulty_distribution.items():
            questions = await self._select_questions(
                subject_id,
                difficulty,
                count,
                knowledge_points,
                db
            )
            selected_questions.extend(questions)
        
        # 调整总分
        self._adjust_total_score(selected_questions, total_score)
        
        return selected_questions

    def _adjust_total_score(self, questions: List[Question], target_score: int):
        """调整题目分数以符合总分要求"""
        current_total = sum(q.score for q in questions)
        ratio = target_score / current_total
        
        for question in questions:
            question.score = round(question.score * ratio, 1)
