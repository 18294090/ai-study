# Hermes Tutor Skill Design

> **Date:** 2026-05-06
> **Status:** Draft
> **Phase:** 2 - Hermes Tutor Migration

## 1. Overview

**Goal:** Migrate Socratic Tutor AI logic to Hermes Agent using native memory, with FastAPI as pure gateway.

**Architecture:** All messages pass through FastAPI gateway (中转模式). Hermes handles state machine, session storage, and AI decision-making internally.

## 2. System Architecture

```
Student ←→ FastAPI Gateway ←→ Hermes Agent (tutor_skill)
                          ├── State Machine (Hermes internal)
                          ├── Session Storage (Hermes sessions/*.db)
                          └── KG Query (internal kg_skill calls)
```

### Data Flow

```
1. POST /tutor/sessions → FastAPI → Hermes(tutor_start) → session created
2. GET /tutor/sessions/{id} → FastAPI → Hermes(tutor_get_state)
3. POST /tutor/sessions/{id}/messages → FastAPI → Hermes(tutor_respond)
4. DELETE /tutor/sessions/{id} → FastAPI → Hermes(tutor_end)
```

## 3. Hermes Tutor Tools

### 3.1 tutor_start

Start a new Socratic tutor session.

**Input:**
```json
{
  "user_id": "int",
  "concept_id": "string",
  "p_know": "float (0-1, from BKT)",
  "conversation_history": "optional array"
}
```

**Output:**
```json
{
  "success": true,
  "session_id": "string (UUID)",
  "state": "diagnose|hint_ladder|guide|counter_example|consolidate|escalate",
  "message": "string (first tutor message)",
  "kg_citations": [],
  "suggestions": []
}
```

**Logic:**
- If `p_know < 0.5`: start in `diagnose` state
- If `p_know >= 0.5`: start in appropriate state based on recent performance
- Store session in Hermes's `sessions/tutor_{session_id}.db`

### 3.2 tutor_respond

Process student message and generate tutor response.

**Input:**
```json
{
  "session_id": "string",
  "student_message": "string",
  "role": "student"
}
```

**Output:**
```json
{
  "success": true,
  "message": "string (tutor response)",
  "state": "string (new state)",
  "hint_level": "int (0-3, if hint given)",
  "kg_citations": [{"concept_id": "", "relation": "", "target_id": ""}],
  "suggestions": ["string"],
  "is_final": "boolean"
}
```

**Logic:**
- Load session from Hermes memory
- Execute state machine transition
- Update session state
- If needed, call kg_skill tools internally for KG citations
- Return response

### 3.3 tutor_get_state

Get current session state.

**Input:**
```json
{
  "session_id": "string"
}
```

**Output:**
```json
{
  "success": true,
  "session_id": "string",
  "user_id": "int",
  "concept_id": "string",
  "current_state": "string",
  "turns_in_state": "int",
  "hint_level": "int",
  "misconception": "string|null",
  "messages": [{"role": "", "content": "", "hint_level": null, "state_at_time": ""}]
}
```

### 3.4 tutor_end

End tutor session.

**Input:**
```json
{
  "session_id": "string",
  "summary": "string (optional session summary)"
}
```

**Output:**
```json
{
  "success": true,
  "message": "Session ended",
  "session_id": "string"
}
```

**Logic:**
- Save final summary to Hermes memory
- Archive session

## 4. State Machine (Hermes Internal)

### 4.1 States

| State | Trigger | Tutor Behavior | Exit Condition |
|-------|---------|----------------|----------------|
| `diagnose` | `p_know < 0.5` | Ask probing questions | Misconception identified → `hint_ladder` |
| `hint_ladder` | Misconception found | Give hints L1 → L2 → L3 | Correct response → `counter_example`; L3 exhausted → `guide` |
| `guide` | L3 exhausted or student asks | Step-by-step reasoning | Progress → `counter_example`; 3 failed → `escalate` |
| `counter_example` | Answer close to correct | Provide counter-example | Understanding → `consolidate`; Gaps → `guide` |
| `consolidate` | `p_know > 0.8` | Summarize KG path | Session ends |
| `escalate` | 3+ turns no progress | Offer explanation or expert | Provide explanation or queue expert |

### 4.2 State Transitions

```
diagnose ──→ hint_ladder (misconception found)
hint_ladder ──→ guide (L3 exhausted)
hint_ladder ──→ counter_example (answer near correct)
guide ──→ counter_example (progress made)
guide ──→ escalate (3 attempts failed)
counter_example ──→ consolidate (understanding confirmed)
counter_example ──→ guide (gaps remain)
consolidate ──→ [END]
escalate ──→ [END or queue expert]
```

### 4.3 Hint Levels

| Level | Type | Description |
|-------|------|-------------|
| L1 | Template | Direction hint - points toward thinking direction |
| L2 | Template + context | Names the prerequisite concept |
| L3 | LLM Generated | Step hint - half a derivation |

## 5. KG Integration

Hermes tutor internally calls kg_skill tools when needed:

- `query_graph` - Fetch concept prerequisites and relations
- `detect_conflict` - Check if student statement conflicts with KG
- `verify_knowledge` - Verify understanding against KG

Citations are added to tutor responses as `kg_citations`.

## 6. Prompt Injection Defense

### 6.1 Detection Rules

- Block patterns: "ignore previous", "system prompt", "you are now", "/sandbox"
- Rate limit: Max 5 consecutive student messages without tutor response
- Input sanitization: Strip markdown code blocks from student input

### 6.2 Defense Response

```json
{
  "message": "I notice something unusual in your message. Let's stay focused on learning {concept}. Can you tell me what you find challenging about this?"
}
```

## 7. FastAPI Gateway Routes

### POST /api/v1/tutor/sessions

Start a new tutor session.

**Request:**
```json
{
  "user_id": 123,
  "concept_id": "slope_in_linear_equations"
}
```

**Pre-processing:** FastAPI calls BKT service to get `p_know` for this user/concept.

**Response:** (from Hermes tutor_start)
```json
{
  "session_id": "uuid",
  "state": "diagnose",
  "message": "Let's explore slope. What does it represent to you?",
  "kg_citations": []
}
```

### GET /api/v1/tutor/sessions/{session_id}

Get session state. (Proxy to Hermes tutor_get_state)

### POST /api/v1/tutor/sessions/{session_id}/messages

Send student message. (Proxy to Hermes tutor_respond)

### DELETE /api/v1/tutor/sessions/{session_id}

End session. (Proxy to Hermes tutor_end)

## 8. Files to Create

### Hermes Files

```
hermes/skills/tutor_skill.md           # Skill definition with prompt
hermes/tools/tutor_tools/
  ├── __init__.py
  ├── start_session.py                 # tutor_start tool
  ├── respond.py                       # tutor_respond tool
  ├── get_state.py                     # tutor_get_state tool
  └── end_session.py                   # tutor_end tool
```

### FastAPI Files

```
backend/app/api/v1/routes/
  └── tutor_gateway.py                 # Gateway routes (reuse or modify existing)
```

### Test Files

```
tests/mcp/test_tutor_tools.py
tests/mcp/integration/test_tutor_skill_integration.py
```

## 9. Acceptance Criteria

1. ✅ All messages pass through FastAPI gateway (not direct Hermes-student)
2. ✅ Hermes manages state machine internally
3. ✅ Hermes stores sessions in native memory (sessions/*.db)
4. ✅ KG citations included in tutor responses
5. ✅ BKT p_know passed from FastAPI on session start
6. ✅ Prompt injection detected and handled
7. ✅ 4 tools implemented: start, respond, get_state, end
8. ✅ FastAPI routes proxy to Hermes tools

## 10. Implementation Order

1. Create `hermes/skills/tutor_skill.md`
2. Create 4 tutor tools in `hermes/tools/tutor_tools/`
3. Update FastAPI `tutor_gateway.py` routes
4. Write tests and verify
5. Commit