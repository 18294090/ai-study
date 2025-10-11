from typing import Dict, List
import jieba
import numpy as np
from collections import Counter

class DifficultyEvaluator:
    def __init__(self):
        self.keyword_weights = {
            "分析": 0.8,
            "证明": 0.9,
            "解释": 0.6,
            "计算": 0.5,
            "选择": 0.3
        }
    
    def evaluate_question(self, content: str, answer: str) -> float:
        """评估题目难度"""
        # 基础分值
        base_score = 3.0
        
        # 分词分析
        words = list(jieba.cut(content + answer))
        word_count = Counter(words)
        
        # 计算关键词权重
        keyword_score = sum(
            self.keyword_weights.get(word, 0)
            for word in word_count
        )
        
        # 计算长度因子
        length_factor = min(len(content) / 100, 2.0)
        
        # 综合评分
        difficulty = base_score + keyword_score * length_factor
        
        # 归一化到1-5分
        return min(max(round(difficulty, 1), 1), 5)

difficulty_evaluator = DifficultyEvaluator()
