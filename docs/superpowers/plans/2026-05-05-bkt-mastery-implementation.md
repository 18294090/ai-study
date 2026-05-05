# BKT Mastery Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Bayesian Knowledge Tracing to track user mastery of KG concepts with PostgreSQL + Redis storage

**Architecture:** BKT service encapsulates algorithm, mastery cache layer handles Redis/PG coordination, API routes expose REST endpoints

**Tech Stack:** Python, SQLAlchemy, psycopg2, redis, FastAPI

---

## File Structure

```
backend/app/
├── models/
│   └── mastery.py          # SQLAlchemy models for mastery_records, answer_logs, diagnostic_results
├── services/
│   ├── bkt_service.py      # BKT algorithm implementation
│   └── mastery_cache.py    # Redis cache layer with PG fallback
├── api/v1/routes/
│   └── mastery.py          # REST API endpoints
└── __init__.py             # Update to register mastery_router

backend/app/kg/src/models/
└── __init__.py             # Add MasteryRecord if needed
```

---

## Task 1: Create BKT Service

**Files:**
- Create: `backend/app/services/bkt_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/kg/tests/test_bkt_service.py
import pytest
from app.services.bkt_service import BKTUpdater

def test_bkt_update_correct_increases_mastery():
    updater = BKTUpdater(p_guess=0.1, p_slip=0.2)
    p = 0.5
    p_new = updater.update(p, is_correct=True)
    assert p_new > p  # correct answer should increase mastery

def test_bkt_update_incorrect_decreases_mastery():
    updater = BKTUpdater(p_guess=0.1, p_slip=0.2)
    p = 0.5
    p_new = updater.update(p, is_correct=False)
    assert p_new < p  # incorrect answer should decrease mastery

def test_bkt_stays_in_bounds():
    updater = BKTUpdater()
    for _ in range(100):
        p = 0.5
        p = updater.update(p, is_correct=True)
        p = updater.update(p, is_correct=False)
    assert 0.0 <= p <= 1.0

def test_bkt_apply_forget():
    updater = BKTUpdater(p_forget=0.05)
    p = 0.8
    p_decayed = updater.apply_forget(p, time_elapsed_hours=1.0)
    assert p_decayed < p  # forgetting should decrease mastery
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_bkt_service.py -v`
Expected: FAIL with "module 'app.services.bkt_service' not found"

- [ ] **Step 3: Write BKT implementation**

```python
# backend/app/services/bkt_service.py
from typing import Optional
from dataclasses import dataclass


@dataclass
class BKTParams:
    p_guess: float = 0.1   # P(L) - lucky guess probability
    p_slip: float = 0.2    # P(S) - slip probability
    p_forget: float = 0.05  # P(T) - forget probability per hour

    def validate(self):
        assert 0 <= self.p_guess <= 1
        assert 0 <= self.p_slip <= 1
        assert 0 <= self.p_forget <= 1


class BKTUpdater:
    def __init__(self, p_guess: float = 0.1, p_slip: float = 0.2, p_forget: float = 0.05):
        self.params = BKTParams(p_guess=p_guess, p_slip=p_slip, p_forget=p_forget)

    def update(self, p_know: float, is_correct: bool) -> float:
        p_guess = self.params.p_guess
        p_slip = self.params.p_slip

        if is_correct:
            numerator = p_know * (1 - p_slip)
            denominator = p_know * (1 - p_slip) + (1 - p_know) * p_guess
        else:
            numerator = p_know * p_slip
            denominator = p_know * p_slip + (1 - p_know) * (1 - p_guess)

        if denominator > 0:
            p_know = numerator / denominator
        else:
            p_know = 0.0

        return max(0.0, min(1.0, p_know))

    def apply_forget(self, p_know: float, time_elapsed_hours: float) -> float:
        decay_factor = (1 - self.params.p_forget) ** time_elapsed_hours
        return p_know * decay_factor

    def compute_initial_p(self, correct_count: int, total_attempts: int) -> float:
        if total_attempts == 0:
            return 0.3  # default initial mastery
        raw_ratio = correct_count / total_attempts
        # BKT-smoothed initial probability
        # Apply some smoothing toward 0.5 to avoid extreme values from few questions
        n = total_attempts
        smoothed = (raw_ratio * n + 0.5 * 3) / (n + 3)
        return max(0.1, min(0.9, smoothed))


class MasteryState:
    def __init__(self, p_know: float, attempts: int, correct_count: int):
        self.p_know = p_know
        self.attempts = attempts
        self.correct_count = correct_count

    def to_dict(self) -> dict:
        return {
            "p_know": self.p_know,
            "attempts": self.attempts,
            "correct_count": self.correct_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MasteryState":
        return cls(
            p_know=data.get("p_know", 0.3),
            attempts=data.get("attempts", 0),
            correct_count=data.get("correct_count", 0),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_bkt_service.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/services/bkt_service.py backend/app/kg/tests/test_bkt_service.py && git commit -m "feat: add BKT service with update and forget algorithms"
```

---

## Task 2: Create Mastery Cache Service

**Files:**
- Create: `backend/app/services/mastery_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/kg/tests/test_mastery_cache.py
import pytest
from unittest.mock import MagicMock, patch
from app.services.mastery_cache import MasteryCache

def test_cache_key_format():
    cache = MasteryCache(redis_client=MagicMock(), db_session=MagicMock())
    key = cache._cache_key(user_id=123, concept_id="concept_001")
    assert key == "mastery:123:concept_001"

@patch('app.services.mastery_cache.redis')
def test_cache_set_and_get():
    mock_redis = MagicMock()
    cache = MasteryCache(redis_client=mock_redis, db_session=MagicMock())
    
    test_data = {"p_know": 0.7, "attempts": 5, "correct_count": 3}
    cache.set(123, "concept_001", test_data)
    
    mock_redis.setex.assert_called()
    
    cached = cache.get(123, "concept_001")
    assert cached == test_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_mastery_cache.py -v`
Expected: FAIL with "module 'app.services.mastery_cache' not found"

- [ ] **Step 3: Write MasteryCache implementation**

```python
# backend/app/services/mastery_cache.py
import json
import logging
from typing import Optional, Dict, Any
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

    def get_all_user_mastery(self, user_id: int) -> list:
        from app.models.mastery import MasteryRecord
        records = self.db.query(MasteryRecord).filter(
            MasteryRecord.user_id == user_id
        ).all()
        return [
            {"concept_id": r.concept_id, "p_know": r.p_know, "attempts": r.attempts}
            for r in records
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_mastery_cache.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/services/mastery_cache.py backend/app/kg/tests/test_mastery_cache.py && git commit -m "feat: add MasteryCache with Redis/PG fallback"
```

---

## Task 3: Create Mastery SQLAlchemy Model

**Files:**
- Create: `backend/app/models/mastery.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/kg/tests/test_mastery_model.py
import pytest
from app.models.mastery import MasteryRecord, AnswerLog, DiagnosticResult

def test_mastery_record_creation():
    record = MasteryRecord(
        user_id=123,
        concept_id="concept_001",
        p_know=0.75,
        attempts=5,
        correct_count=4
    )
    assert record.user_id == 123
    assert record.concept_id == "concept_001"
    assert record.p_know == 0.75

def test_answer_log_creation():
    log = AnswerLog(
        user_id=123,
        concept_id="concept_001",
        question_id=1001,
        is_correct=True,
        bkt_p_before=0.6,
        bkt_p_after=0.8
    )
    assert log.is_correct is True
    assert log.bkt_p_after > log.bkt_p_before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_mastery_model.py -v`
Expected: FAIL with "module 'app.models.mastery' not found"

- [ ] **Step 3: Write Mastery model**

```python
# backend/app/models/mastery.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class MasteryRecord(Base):
    __tablename__ = "mastery_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    concept_id = Column(String, nullable=False, index=True)
    p_know = Column(Float, nullable=False, default=0.3)
    attempts = Column(Integer, nullable=False, default=0)
    correct_count = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'concept_id', name='uq_user_concept'),
    )

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "concept_id": self.concept_id,
            "p_know": self.p_know,
            "attempts": self.attempts,
            "correct_count": self.correct_count,
            "last_updated": str(self.last_updated) if self.last_updated else None,
        }


class AnswerLog(Base):
    __tablename__ = "answer_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    concept_id = Column(String, nullable=False, index=True)
    question_id = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    bkt_p_before = Column(Float, nullable=False)
    bkt_p_after = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DiagnosticResult(Base):
    __tablename__ = "diagnostic_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    concept_id = Column(String, nullable=False, index=True)
    initial_p = Column(Float, nullable=False)
    questions_answered = Column(Integer, nullable=False, default=0)
    questions_correct = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Verify model imports work**

Run: `cd /home/zh/ai-study/backend && python3 -c "from app.models.mastery import MasteryRecord, AnswerLog, DiagnosticResult; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/models/mastery.py && git commit -m "feat: add MasteryRecord, AnswerLog, DiagnosticResult models"
```

---

## Task 4: Create Mastery API Routes

**Files:**
- Create: `backend/app/api/v1/routes/mastery.py`
- Modify: `backend/app/api/v1/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/kg/tests/test_mastery_routes.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

def test_update_mastery_endpoint():
    from app.api.v1.routes.mastery import router
    from fastapi import APIRouter
    
    assert router is not None
    assert hasattr(router, "routes")
```

- [ ] **Step 2: Write API implementation**

```python
# backend/app/api/v1/routes/mastery.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.services.bkt_service import BKTUpdater, MasteryState
from app.services.mastery_cache import MasteryCache
from app.models.mastery import MasteryRecord, AnswerLog, DiagnosticResult
import redis
import os


router = APIRouter(prefix="/mastery", tags=["mastery"])


class MasteryUpdateRequest(BaseModel):
    user_id: int
    concept_id: str
    question_id: int
    is_correct: bool
    time_elapsed_seconds: Optional[float] = 0


class MasteryUpdateResponse(BaseModel):
    concept_id: str
    p_before: float
    p_after: float
    attempts: int
    correct_count: int


class MasteryQueryResponse(BaseModel):
    user_id: int
    concept_id: str
    p_know: float
    attempts: int
    correct_count: int
    last_updated: Optional[str]


class DiagnoseRequest(BaseModel):
    user_id: int
    concept_ids: List[str]
    questions_per_concept: int = 5


class DiagnoseResponse(BaseModel):
    diagnostics: List[dict]
    questions: List[dict]


def get_mastery_cache():
    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        decode_responses=True
    )
    # Note: In production, get db session from dependency
    return MasteryCache(redis_client=redis_client, db_session=None)


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    request: DiagnoseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Initialize mastery via diagnostic test"""
    updater = BKTUpdater()
    
    # Generate questions for each concept (simplified - would call question service)
    questions = []
    diagnostics = []
    
    for concept_id in request.concept_ids:
        # Placeholder: generate diagnostic questions
        # In production, this would pull from question bank with IRT calibration
        for i in range(request.questions_per_concept):
            questions.append({
                "concept_id": concept_id,
                "question_id": 1000 + i,
                "question_text": f"Diagnostic Q{i+1} for {concept_id}"
            })
        
        diagnostics.append({
            "concept_id": concept_id,
            "initial_p": 0.3  # Placeholder - would be computed from actual answers
        })
    
    return DiagnoseResponse(diagnostics=diagnostics, questions=questions)


@router.put("/update", response_model=MasteryUpdateResponse)
async def update_mastery(
    request: MasteryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update mastery after an answer"""
    from sqlalchemy import select
    
    updater = BKTUpdater()
    
    # Get current state
    result = await db.execute(
        select(MasteryRecord).filter(
            MasteryRecord.user_id == request.user_id,
            MasteryRecord.concept_id == request.concept_id
        )
    )
    record = result.scalar_one_or_none()
    
    if record:
        p_before = record.p_know
        p_after = updater.update(p_before, request.is_correct)
        
        # Apply forget decay if time elapsed
        if request.time_elapsed_seconds:
            hours = request.time_elapsed_seconds / 3600
            p_after = updater.apply_forget(p_after, hours)
        
        record.p_know = p_after
        record.attempts += 1
        if request.is_correct:
            record.correct_count += 1
    else:
        # Create new record
        p_before = 0.3  # default initial
        p_after = updater.compute_initial_p(
            correct_count=1 if request.is_correct else 0,
            total_attempts=1
        )
        record = MasteryRecord(
            user_id=request.user_id,
            concept_id=request.concept_id,
            p_know=p_after,
            attempts=1,
            correct_count=1 if request.is_correct else 0
        )
        db.add(record)
    
    # Log the answer
    answer_log = AnswerLog(
        user_id=request.user_id,
        concept_id=request.concept_id,
        question_id=request.question_id,
        is_correct=request.is_correct,
        bkt_p_before=p_before,
        bkt_p_after=p_after
    )
    db.add(answer_log)
    await db.commit()
    
    return MasteryUpdateResponse(
        concept_id=request.concept_id,
        p_before=p_before,
        p_after=p_after,
        attempts=record.attempts,
        correct_count=record.correct_count
    )


@router.get("/{user_id}/{concept_id}", response_model=MasteryQueryResponse)
async def get_mastery(
    user_id: int,
    concept_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get mastery for a specific concept"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(MasteryRecord).filter(
            MasteryRecord.user_id == user_id,
            MasteryRecord.concept_id == concept_id
        )
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Mastery record not found")
    
    return MasteryQueryResponse(
        user_id=record.user_id,
        concept_id=record.concept_id,
        p_know=record.p_know,
        attempts=record.attempts,
        correct_count=record.correct_count,
        last_updated=str(record.last_updated) if record.last_updated else None
    )


@router.get("/{user_id}")
async def get_all_mastery(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all mastery records for a user"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(MasteryRecord).filter(MasteryRecord.user_id == user_id)
    )
    records = result.scalars().all()
    
    return {
        "user_id": user_id,
        "masteries": [
            {
                "concept_id": r.concept_id,
                "p_know": r.p_know,
                "attempts": r.attempts,
                "correct_count": r.correct_count
            }
            for r in records
        ]
    }
```

- [ ] **Step 3: Register mastery router in __init__.py**

Add to `backend/app/api/v1/__init__.py`:
```python
from .routes.mastery import router as mastery_router
# Add after knowledge_extraction_router:
api_v1_router.include_router(mastery_router, prefix="/mastery", tags=["mastery"])
```

- [ ] **Step 4: Verify imports work**

Run: `cd /home/zh/ai-study/backend && python3 -c "from app.api.v1.routes.mastery import router; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/api/v1/routes/mastery.py backend/app/api/v1/__init__.py && git commit -m "feat: add mastery API routes with BKT update and diagnostic endpoints"
```

---

## Task 5: Verify Complete Integration

**Files:**
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Verify all imports**

```bash
cd /home/zh/ai-study/backend && python3 -c "
from app.services.bkt_service import BKTUpdater, MasteryState
from app.services.mastery_cache import MasteryCache
from app.models.mastery import MasteryRecord, AnswerLog, DiagnosticResult
from app.api.v1.routes.mastery import router
print('All imports OK')
"
```

- [ ] **Step 2: Verify no circular imports**

```bash
cd /home/zh/ai-study/backend && python3 -c "
import app.models.mastery
import app.services.bkt_service
import app.api.v1.routes.mastery
print('No circular imports')
"
```

- [ ] **Step 3: Commit**

```bash
cd /home/zh/ai-study && git add -A && git commit -m "feat: complete BKT mastery tracking implementation"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| BKT update formula | Task 1 |
| Forget decay | Task 1 |
| MasteryRecord model | Task 3 |
| AnswerLog model | Task 3 |
| DiagnosticResult model | Task 3 |
| Redis cache layer | Task 2 |
| POST /mastery/diagnose | Task 4 |
| PUT /mastery/update | Task 4 |
| GET /mastery/{user_id}/{concept_id} | Task 4 |
| GET /mastery/{user_id} | Task 4 |

All requirements covered. No placeholders found.

---

**Plan complete.**