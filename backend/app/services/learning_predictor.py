from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime, timedelta

class LearningPredictor:
    def __init__(self):
        self.model = LinearRegression()
    
    async def predict_progress(
        self,
        user_id: int,
        subject_id: int,
        study_history: List[dict],
        target_days: int = 30
    ) -> Dict:
        """预测学习进度"""
        # 提取历史数据特征
        X, y = self._prepare_training_data(study_history)
        
        if len(X) < 5:  # 数据不足
            return {
                "prediction": None,
                "confidence": 0,
                "message": "需要更多学习数据来进行准确预测"
            }
        
        # 训练模型
        self.model.fit(X, y)
        
        # 预测未来进度
        future_dates = self._generate_future_dates(target_days)
        predictions = self.model.predict(self._prepare_prediction_features(future_dates))
        
        return {
            "prediction": predictions.tolist(),
            "dates": future_dates,
            "confidence": self._calculate_confidence(predictions)
        }
