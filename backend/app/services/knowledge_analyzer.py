from typing import List, Dict
import numpy as np
from sklearn.cluster import DBSCAN
from app.models.knowledge_point import KnowledgePoint

class KnowledgeAnalyzer:
    async def analyze_mastery(
        self,
        user_id: int,
        knowledge_points: List[KnowledgePoint],
        user_answers: List[dict]
    ) -> Dict:
        """分析知识点掌握程度"""
        mastery_scores = {}
        for kp in knowledge_points:
            # 计算正确率
            kp_answers = [a for a in user_answers if a['knowledge_point_id'] == kp.id]
            if kp_answers:
                correct_rate = sum(a['is_correct'] for a in kp_answers) / len(kp_answers)
                
                # 考虑时间因素
                time_weights = self._calculate_time_weights(kp_answers)
                
                # 计算最终掌握度
                mastery_scores[kp.id] = self._calculate_final_score(
                    correct_rate,
                    time_weights,
                    len(kp_answers)
                )
        
        return {
            "mastery_scores": mastery_scores,
            "weak_points": self._identify_weak_points(mastery_scores),
            "recommendations": self._generate_recommendations(mastery_scores)
        }
