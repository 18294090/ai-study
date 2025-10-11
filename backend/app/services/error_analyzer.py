from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.question import Question
from datetime import datetime, timedelta
import numpy as np

class ErrorAnalyzer:
    async def generate_error_report(
        self,
        user_id: int,
        subject_id: int,
        days: int,
        db: AsyncSession
    ) -> Dict:
        """生成错题分析报告"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # 获取错题记录
        errors = await self._get_error_records(
            user_id,
            subject_id,
            start_date,
            end_date,
            db
        )
        
        # 分析错误模式
        error_patterns = self._analyze_error_patterns(errors)
        
        # 生成改进建议
        recommendations = self._generate_recommendations(error_patterns)
        
        return {
            "error_patterns": error_patterns,
            "recommendations": recommendations,
            "trend": self._calculate_error_trend(errors),
            "knowledge_points": self._identify_weak_points(errors)
        }

    def _analyze_error_patterns(self, errors: List[Dict]) -> Dict:
        """分析错误模式"""
        patterns = {}
        for error in errors:
            pattern = self._classify_error(error)
            patterns[pattern] = patterns.get(pattern, 0) + 1
        return patterns
