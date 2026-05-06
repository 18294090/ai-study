# Tutor Skill

## Purpose
Socratic Tutor Agent using state machine to guide students through learning without giving direct answers. All state managed in Hermes native memory.

## Capabilities
- Start tutor sessions with BKT p_know integration
- Process student messages with state machine transitions
- Generate Socratic hints (L1/L2/L3)
- Provide KG-cited responses
- Detect prompt injection attempts

## Tools

### tutor_start
Start a new Socratic tutor session.
- Input: user_id, concept_id, p_know, conversation_history
- Output: session_id, state, message, kg_citations, suggestions

### tutor_respond
Process student message and generate tutor response.
- Input: session_id, student_message, role
- Output: message, state, hint_level, kg_citations, suggestions, is_final

### tutor_get_state
Get current session state.
- Input: session_id
- Output: full session state with messages

### tutor_end
End tutor session.
- Input: session_id, summary
- Output: confirmation

## State Machine

6 states: diagnose, hint_ladder, guide, counter_example, consolidate, escalate

Initial state: p_know < 0.5 → diagnose; else → adaptive

## Memory Integration
Sessions stored in Hermes sessions/tutor_{session_id}.db

## KG Integration
Internally calls kg_skill tools for:
- query_graph: Fetch concept prerequisites
- detect_conflict: Check statement conflicts
- verify_knowledge: Verify understanding

## Prompt Injection Defense
- Block: "ignore previous", "system prompt", "you are now", "/sandbox"
- Rate limit: Max 5 consecutive student messages
- Sanitize: Strip markdown code blocks

## Response Format
Every response includes:
- message: str
- state: str
- kg_citations: [{concept_id, relation, target_id}]
- suggestions: [str]
- hint_level: int (0-3)
- is_final: bool
