import json
import logging
from typing import Optional, Dict, Any, List
from redis import Redis
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MasteryCache:
    CACHE_TTL = 300  # 5 minutes

    def __init__(self, redis_client: Redis, db_session: Session):
        self.redis = redis_client
        self.db = db_session

    def _cache_key(self, user_id: int, concept_id: str) -> str:
        return f"mastery:{user_id}:{concept_id}"

    def get(self, user_id: int, concept_id: str) -> Optional[Dict[str, Any]]:
        key = self._cache_key(user_id, concept_id)
        try:
            cached = self.redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis get failed for {key}: {e}")

        # Fallback to database
        from app.models.mastery import MasteryRecord
        record = self.db.query(MasteryRecord).filter(
            MasteryRecord.user_id == user_id,
            MasteryRecord.concept_id == concept_id
        ).first()

        if record:
            data = {
                "p_know": record.p_know,
                "attempts": record.attempts,
                "correct_count": record.correct_count,
            }
            # Re-cache for next request
            self.set(user_id, concept_id, data)
            return data

        return None

    def set(self, user_id: int, concept_id: str, data: Dict[str, Any], ttl: int = None) -> bool:
        key = self._cache_key(user_id, concept_id)
        try:
            self.redis.setex(
                key,
                ttl or self.CACHE_TTL,
                json.dumps(data)
            )
            return True
        except Exception as e:
            logger.warning(f"Redis set failed for {key}: {e}")
            return False

    def invalidate(self, user_id: int, concept_id: str) -> bool:
        key = self._cache_key(user_id, concept_id)
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed for {key}: {e}")
            return False

    def get_all_user_mastery(self, user_id: int) -> List[Dict[str, Any]]:
        from app.models.mastery import MasteryRecord
        records = self.db.query(MasteryRecord).filter(
            MasteryRecord.user_id == user_id
        ).all()
        return [
            {"concept_id": r.concept_id, "p_know": r.p_know, "attempts": r.attempts}
            for r in records
        ]
