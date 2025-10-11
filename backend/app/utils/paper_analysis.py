from typing import List
from app.models.question import Question
from app.models.knowledge_point import KnowledgePoint
import numpy as np

def calculate_difficulty_score(questions: List[Question]) -> float:
    """计算试卷难度分数"""
    if not questions:
        return 0.0
    
    weights = np.array([q.score for q in questions])
    difficulties = np.array([q.difficulty for q in questions])
    
    # 加权平均难度
    weighted_difficulty = np.sum(weights * difficulties) / np.sum(weights)
    return round(weighted_difficulty, 2)

def analyze_question_types(questions: List[Question]) -> dict:
    """分析题型分布"""
    type_count = {}
    for question in questions:
        type_count[question.question_type] = type_count.get(question.question_type, 0) + 1
    return type_count

def estimate_completion_time(questions: List[Question]) -> int:
    """估算完成时间（分钟）"""
    base_times = {
        "选择题": 2,
        "填空题": 3,
        "简答题": 8,
        "论述题": 15
    }
    
    total_time = sum(base_times.get(q.question_type, 5) * (q.difficulty / 3) 
                    for q in questions)
    return round(total_time)
