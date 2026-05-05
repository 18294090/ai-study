# BKT Mastery Tracking Implementation Spec

> **Date:** 2026-05-05
> **Status:** Approved
> **Version:** 1.0

## 1. Overview

**Goal:** Implement Bayesian Knowledge Tracing (BKT) to track each user's mastery probability `p ∈ [0,1]` for every KG concept, with real-time updates on correct/incorrect answers and explainable diagnostics via KG paths.

**Storage:** PostgreSQL (persistent) + Redis (hot cache)

---

## 2. Data Model

### 2.1 PostgreSQL Tables

```sql
-- Mastery records: one row per (user, concept)
CREATE TABLE mastery_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    concept_id TEXT NOT NULL,  -- KG concept node id
    p_know FLOAT NOT NULL DEFAULT 0.3,  -- current mastery probability
    attempts INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, concept_id)
);

-- Answer logs for BKT learning
CREATE TABLE answer_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    concept_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL,
    bkt_p_before FLOAT NOT NULL,  -- p_know before this answer
    bkt_p_after FLOAT NOT NULL,   -- p_know after BKT update
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Diagnostic test results (for initializing mastery)
CREATE TABLE diagnostic_results (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    concept_id TEXT NOT NULL,
    initial_p FLOAT NOT NULL,  -- p_initial from diagnostic
    questions_answered INTEGER NOT NULL,
    questions_correct INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 2.2 Redis Cache

| Key Pattern | Value | TTL |
|-------------|-------|-----|
| `mastery:{user_id}:{concept_id}` | JSON: `{"p_know": 0.7, "attempts": 5, "correct_count": 3}` | 5 min |

---

## 3. BKT Algorithm

### 3.1 Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `P(L)` | 0.1 | Probability of lucky guess (correct without knowing) |
| `P(S)` | 0.2 | Probability of slip (mistake despite knowing) |
| `P(T)` | 0.05 | Transfer (forget) probability per time unit |
| `p_initial` | from diagnostic | Initial mastery before any exercises |

### 3.2 Update Rule

On correct answer:
```
P(K) = (P(K) * (1 - P(S))) / (P(K) * (1 - P(S)) + (1 - P(K)) * P(L))
```

On incorrect answer:
```
P(K) = (P(K) * P(S)) / (P(K) * P(S) + (1 - P(K)) * (1 - P(L)))
```

After update:
```
P(K) = P(K) * (1 - P(T))  -- apply forget decay if time elapsed
```

### 3.3 Implementation

```python
class BKTUpdater:
    def __init__(self, p_guess=0.1, p_slip=0.2, p_forget=0.05):
        self.p_guess = p_guess
        self.p_slip = p_slip
        self.p_forget = p_forget

    def update(self, p_know: float, is_correct: bool) -> float:
        if is_correct:
            # P(K) = P(K) * (1-P(S)) / (P(K)*(1-P(S)) + (1-P(K))*P(L))
            numerator = p_know * (1 - self.p_slip)
            denominator = p_know * (1 - self.p_slip) + (1 - p_know) * self.p_guess
        else:
            # P(K) = P(K) * P(S) / (P(K)*P(S) + (1-P(K))*(1-P(L)))
            numerator = p_know * self.p_slip
            denominator = p_know * self.p_slip + (1 - p_know) * (1 - self.p_guess)

        p_know = numerator / denominator if denominator > 0 else 0.0
        return max(0.0, min(1.0, p_know))

    def apply_forget(self, p_know: float, time_elapsed_hours: float) -> float:
        decay_factor = (1 - self.p_forget) ** time_elapsed_hours
        return p_know * decay_factor
```

---

## 4. API Endpoints

### 4.1 Diagnostic Test Init

**POST** `/api/v1/mastery/diagnose`

Request:
```json
{
  "user_id": 123,
  "concept_ids": ["concept_001", "concept_002"],
  "questions_per_concept": 5
}
```

Response:
```json
{
  "diagnostics": [
    {"concept_id": "concept_001", "initial_p": 0.65},
    {"concept_id": "concept_002", "initial_p": 0.40}
  ],
  "questions": [
    {"concept_id": "concept_001", "question_id": 1001, "question_text": "..."},
    ...
  ]
}
```

### 4.2 Update Mastery (after answer)

**PUT** `/api/v1/mastery/update`

Request:
```json
{
  "user_id": 123,
  "concept_id": "concept_001",
  "question_id": 1001,
  "is_correct": true,
  "time_elapsed_seconds": 3600
}
```

Response:
```json
{
  "concept_id": "concept_001",
  "p_before": 0.65,
  "p_after": 0.82,
  "attempts": 2,
  "correct_count": 2
}
```

### 4.3 Get Single Mastery

**GET** `/api/v1/mastery/{user_id}/{concept_id}`

Response:
```json
{
  "user_id": 123,
  "concept_id": "concept_001",
  "p_know": 0.82,
  "attempts": 2,
  "correct_count": 2,
  "last_updated": "2026-05-05T10:30:00Z"
}
```

### 4.4 Get All User Mastery

**GET** `/api/v1/mastery/{user_id}`

Response:
```json
{
  "user_id": 123,
  "masteries": [
    {"concept_id": "concept_001", "p_know": 0.82, "attempts": 2},
    {"concept_id": "concept_002", "p_know": 0.40, "attempts": 1}
  ]
}
```

---

## 5. Diagnostic Test Flow

1. **Start diagnostic:** `POST /mastery/diagnose` with concept_ids
2. **System generates questions:** target each concept, difficulty calibrated via IRT
3. **User answers questions:** each answer triggers `PUT /mastery/update` with `is_correct`
4. **Diagnostic complete:** after N questions per concept, system computes `p_initial` as ratio of correct answers (with BKT smoothing)
5. **Initialize mastery:** `p_initial` stored in PG and cached in Redis

---

## 6. Cache Strategy

| Operation | Cache | DB |
|-----------|-------|-----|
| Read | Redis first, fallback PG | Write-through |
| Update | Write to Redis immediately | Async flush every 60s |
| Expiry | TTL 5 min, refresh on read | Permanent until updated |

---

## 7. Explainability

Every mastery query returns KG path context:

```json
{
  "p_know": 0.40,
  "explanation": "Concept X has mastery 0.4 because prerequisite Y has mastery 0.5 (only 50%), and X requires Y. Recommended action: practice Y first.",
  "kg_path": ["concept_Y", "requires", "concept_X"]
}
```

---

## 8. Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/app/api/v1/routes/mastery.py` | Create | API endpoints |
| `backend/app/services/bkt_service.py` | Create | BKT algorithm + update logic |
| `backend/app/services/mastery_cache.py` | Create | Redis cache layer |
| `backend/app/models/mastery.py | Create | SQLAlchemy models |
| `backend/app/api/v1/__init__.py` | Modify | Register mastery_router |
| `backend/app/kg/src/models/__init__.py` | Modify | Add MasteryRecord model |

---

## 9. Acceptance Criteria

1. ✅ Diagnostic test initializes `p_initial` per concept
2. ✅ Correct/incorrect answers update `p_know` via BKT formula
3. ✅ Mastery data cached in Redis (5min TTL)
4. ✅ PostgreSQL persistence with answer_logs for audit
5. ✅ `GET /mastery/{user_id}/{concept_id}` returns current mastery
6. ✅ All API endpoints return proper JSON responses
7. ✅ BKT parameters configurable (P(L), P(S), P(T))
8. ✅ Forget decay applied based on time elapsed