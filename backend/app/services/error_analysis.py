from typing import Dict, List
from collections import defaultdict
import numpy as np
from sklearn.cluster import KMeans

class ErrorAnalyzer:
    def __init__(self):
        self.patterns = defaultdict(int)
        self.clusters = {}
    
    async def analyze_error_patterns(self, user_answers: List[dict]) -> Dict:
        """分析错误模式"""
        error_vectors = []
        for answer in user_answers:
            if not answer['is_correct']:
                error_vector = self._extract_error_features(answer)
                error_vectors.append(error_vector)
        
        if error_vectors:
            # 使用K-means聚类分析错误模式
            kmeans = KMeans(n_clusters=min(3, len(error_vectors)))
            clusters = kmeans.fit_predict(error_vectors)
            
            # 解释每个错误类型
            return self._interpret_error_clusters(clusters, error_vectors)
        
        return {"error_patterns": [], "recommendations": []}
