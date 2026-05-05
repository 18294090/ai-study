import pytest
import sys
sys.path.insert(0, '/home/zh/ai-study/backend')

from unittest.mock import MagicMock, patch
from app.services.mastery_cache import MasteryCache


def test_cache_key_format():
    mock_redis = MagicMock()
    mock_db = MagicMock()
    cache = MasteryCache(redis_client=mock_redis, db_session=mock_db)
    key = cache._cache_key(user_id=123, concept_id="concept_001")
    assert key == "mastery:123:concept_001"


def test_cache_set_and_get():
    mock_redis = MagicMock()
    mock_db = MagicMock()
    cache = MasteryCache(redis_client=mock_redis, db_session=mock_db)
    
    test_data = {"p_know": 0.7, "attempts": 5, "correct_count": 3}
    result = cache.set(123, "concept_001", test_data)
    assert result is True
    mock_redis.setex.assert_called()


def test_cache_get_returns_cached_data():
    mock_redis = MagicMock()
    mock_redis.get.return_value = '{"p_know": 0.75, "attempts": 4, "correct_count": 3}'
    mock_db = MagicMock()
    cache = MasteryCache(redis_client=mock_redis, db_session=mock_db)
    
    result = cache.get(123, "concept_001")
    assert result == {"p_know": 0.75, "attempts": 4, "correct_count": 3}


def test_cache_get_returns_none_on_miss():
    import sys
    from unittest.mock import MagicMock
    mock_mastery_module = MagicMock()
    mock_mastery_module.MasteryRecord = MagicMock()
    sys.modules['app.models.mastery'] = mock_mastery_module
    
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    cache = MasteryCache(redis_client=mock_redis, db_session=mock_db)
    
    result = cache.get(999, "nonexistent")
    assert result is None


def test_cache_invalidate():
    mock_redis = MagicMock()
    mock_db = MagicMock()
    cache = MasteryCache(redis_client=mock_redis, db_session=mock_db)
    
    result = cache.invalidate(123, "concept_001")
    assert result is True
    mock_redis.delete.assert_called_with("mastery:123:concept_001")
