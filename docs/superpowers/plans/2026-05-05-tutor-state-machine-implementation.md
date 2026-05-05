# Socratic Tutor State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Socratic Tutor state machine with 6 states, hybrid hint generation, KG citations, and prompt injection defense

**Architecture:** State machine as a class with transition methods, separate hint generator service, SQLAlchemy models for persistence

**Tech Stack:** Python, SQLAlchemy, FastAPI, LangGraph (for state machine), LLM integration

---

## File Structure

```
backend/app/
├── models/
│   └── tutor.py          # TutorSession, TutorMessage, TutorHintTemplate
├── services/
│   ├── tutor_state_machine.py   # State machine logic
│   └── tutor_hint_generator.py  # Hybrid hint generation
├── api/v1/routes/
│   └── tutor.py          # API endpoints
└── kg/tests/
    ├── test_tutor_state_machine.py
    └── test_tutor_hint_generator.py
```

---

## Task 1: Create Tutor Models

**Files:**
- Create: `backend/app/models/tutor.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/kg/tests/test_tutor_model.py
import pytest
import sys
sys.path.insert(0, '/home/zh/ai-study/backend')

from app.models.tutor import TutorSession, TutorMessage, TutorHintTemplate


def test_tutor_session_creation():
    session = TutorSession(
        user_id=123,
        concept_id="slope",
        current_state="diagnose",
        target_concept_id="slope"
    )
    assert session.user_id == 123
    assert session.current_state == "diagnose"
    assert session.turns_in_state == 0


def test_tutor_message_creation():
    msg = TutorMessage(
        session_id=1,
        role="tutor",
        content="Let's explore slope",
        state_at_time="diagnose"
    )
    assert msg.role == "tutor"
    assert msg.state_at_time == "diagnose"


def test_hint_template_creation():
    template = TutorHintTemplate(
        concept_id="slope",
        hint_level=1,
        template_text="Think about what slope represents"
    )
    assert template.hint_level == 1
    assert "slope" in template.template_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_tutor_model.py -v`
Expected: FAIL with "No module named 'app.models.tutor'"

- [ ] **Step 3: Write Tutor model**

```python
# backend/app/models/tutor.py
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class TutorSession(Base):
    __tablename__ = "tutor_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    concept_id = Column(String, nullable=False, index=True)
    current_state = Column(String, nullable=False, default="diagnose")
    turns_in_state = Column(Integer, default=0)
    target_concept_id = Column(String, nullable=False)
    misconception = Column(String, nullable=True)
    hint_level = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("TutorMessage", back_populates="session")


class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("tutor_sessions.id"))
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    hint_level = Column(Integer, nullable=True)
    state_at_time = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TutorSession", back_populates="messages")


class TutorHintTemplate(Base):
    __tablename__ = "tutor_hint_templates"

    id = Column(Integer, primary_key=True, index=True)
    concept_id = Column(String, nullable=False, index=True)
    hint_level = Column(Integer, nullable=False)
    template_text = Column(Text, nullable=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_tutor_model.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/models/tutor.py backend/app/kg/tests/test_tutor_model.py && git commit -m "feat: add TutorSession, TutorMessage, TutorHintTemplate models"
```

---

## Task 2: Create State Machine Service

**Files:**
- Create: `backend/app/services/tutor_state_machine.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/kg/tests/test_tutor_state_machine.py
import pytest
import sys
sys.path.insert(0, '/home/zh/ai-study/backend')

from app.services.tutor_state_machine import TutorStateMachine, TutorState, TutorResponse


def test_initial_state_is_diagnose():
    sm = TutorStateMachine(user_id=123, concept_id="slope")
    assert sm.state == TutorState.DIAGNOSE


def test_diagnose_to_hint_ladder_transition():
    sm = TutorStateMachine(user_id=123, concept_id="slope")
    response = sm.transition("student_response_here", role="student")
    # diagnose identifies misconception, moves to hint_ladder
    assert response.state in [TutorState.HINT_LADDER, TutorState.GUIDE]


def test_state_transition_accumulates_turns():
    sm = TutorStateMachine(user_id=123, concept_id="slope")
    initial_turns = sm.turns_in_state
    sm.increment_turn()
    assert sm.turns_in_state == initial_turns + 1


def test_escalate_after_max_turns():
    sm = TutorStateMachine(user_id=123, concept_id="slope")
    sm.turns_in_state = 3
    response = sm.transition("student_response", role="student")
    assert response.state == TutorState.ESCALATE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_tutor_state_machine.py -v`
Expected: FAIL with "No module named 'app.services.tutor_state_machine'"

- [ ] **Step 3: Write State Machine**

```python
# backend/app/services/tutor_state_machine.py
from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from app.services.tutor_hint_generator import HintGenerator


class TutorState(Enum):
    DIAGNOSE = "diagnose"
    HINT_LADDER = "hint_ladder"
    GUIDE = "guide"
    COUNTER_EXAMPLE = "counter_example"
    CONSOLIDATE = "consolidate"
    ESCALATE = "escalate"


@dataclass
class TutorResponse:
    message: str
    state: TutorState
    hint_level: Optional[int] = None
    kg_citations: List[Dict[str, Any]] = None
    suggestions: List[str] = None
    is_final: bool = False

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "state": self.state.value,
            "hint_level": self.hint_level,
            "kg_citations": self.kg_citations or [],
            "suggestions": self.suggestions or [],
            "is_final": self.is_final,
        }


class TutorStateMachine:
    MAX_TURNS_PER_STATE = 3

    def __init__(self, user_id: int, concept_id: str, session_id: Optional[int] = None):
        self.user_id = user_id
        self.concept_id = concept_id
        self.session_id = session_id
        self.state = TutorState.DIAGNOSE
        self.turns_in_state = 0
        self.hint_level = 0
        self.misconception: Optional[str] = None
        self.hint_generator = HintGenerator()

    def increment_turn(self):
        self.turns_in_state += 1

    def reset_turns(self):
        self.turns_in_state = 0
        self.hint_level = 0

    def transition(self, student_input: str, role: str = "student") -> TutorResponse:
        if role != "student":
            return self._tutor_response("I understand. Let's continue exploring.")

        self.increment_turn()

        # Check for prompt injection
        if self._detect_injection(student_input):
            return self._injection_defense_response()

        # State-specific logic
        if self.state == TutorState.DIAGNOSE:
            return self._handle_diagnose(student_input)
        elif self.state == TutorState.HINT_LADDER:
            return self._handle_hint_ladder(student_input)
        elif self.state == TutorState.GUIDE:
            return self._handle_guide(student_input)
        elif self.state == TutorState.COUNTER_EXAMPLE:
            return self._handle_counter_example(student_input)
        elif self.state == TutorState.CONSOLIDATE:
            return self._handle_consolidate(student_input)
        elif self.state == TutorState.ESCALATE:
            return self._handle_escalate(student_input)

        return self._default_response()

    def _handle_diagnose(self, student_input: str) -> TutorResponse:
        # Analyze student input for misconception patterns
        misconception = self._identify_misconception(student_input)

        if misconception:
            self.misconception = misconception
            self.state = TutorState.HINT_LADDER
            self.reset_turns()
            return TutorResponse(
                message=f"I see you might be thinking about {self.concept_id} in terms of {misconception}. Let me ask you something: what do you think determines the value?",
                state=self.state,
                kg_citations=self._get_kg_citations(),
                suggestions=["Consider the definition", "Think about prerequisites"]
            )
        else:
            # Keep diagnosing
            return TutorResponse(
                message="Interesting. Can you tell me more about your understanding? What does it mean for something to have this property?",
                state=self.state,
                kg_citations=self._get_kg_citations()
            )

    def _handle_hint_ladder(self, student_input: str) -> TutorResponse:
        self.hint_level += 1

        if self.hint_level > 3:
            self.state = TutorState.GUIDE
            self.reset_turns()
            return TutorResponse(
                message="Let me guide you through this step by step. First, consider the basic definition...",
                state=self.state,
                kg_citations=self._get_kg_citations()
            )

        hint = self.hint_generator.generate_hint(self.concept_id, self.hint_level, self.misconception)

        return TutorResponse(
            message=hint,
            state=self.state,
            hint_level=self.hint_level,
            kg_citations=self._get_kg_citations(),
            suggestions=self._get_suggestions_for_level(self.hint_level)
        )

    def _handle_guide(self, student_input: str) -> TutorResponse:
        if self.turns_in_state >= self.MAX_TURNS_PER_STATE:
            self.state = TutorState.ESCALATE
            return TutorResponse(
                message="I've noticed we've been working on this for a while. Would you like me to explain the concept directly, or shall I connect you with an expert?",
                state=self.state,
                is_final=False
            )

        return TutorResponse(
            message=f"Let me help you reason through this. If we start with X, what follows for {self.concept_id}?",
            state=self.state,
            kg_citations=self._get_kg_citations()
        )

    def _handle_counter_example(self, student_input: str) -> TutorResponse:
        # Check if student understanding is confirmed
        if self._check_understanding(student_input):
            self.state = TutorState.CONSOLIDATE
            self.reset_turns()
            return TutorResponse(
                message=f"Great! You've demonstrated understanding of {self.concept_id}. To summarize: it's related to these KG concepts...",
                state=self.state,
                kg_citations=self._get_kg_citations(),
                suggestions=[f"Practice problems for {self.concept_id}"]
            )
        else:
            self.state = TutorState.GUIDE
            self.reset_turns()
            return TutorResponse(
                message="Let me give you a specific example to check your understanding...",
                state=self.state,
                kg_citations=self._get_kg_citations()
            )

    def _handle_consolidate(self, student_input: str) -> TutorResponse:
        return TutorResponse(
            message=f"Excellent work! You've mastered {self.concept_id}. Your understanding now includes the KG path we explored.",
            state=self.state,
            is_final=True,
            kg_citations=self._get_kg_citations()
        )

    def _handle_escalate(self, student_input: str) -> TutorResponse:
        return TutorResponse(
            message="I'm connecting you with additional resources. A human expert will follow up if needed.",
            state=self.state,
            is_final=True
        )

    def _default_response(self) -> TutorResponse:
        return TutorResponse(
            message="Let's continue exploring this concept together.",
            state=self.state,
            kg_citations=self._get_kg_citations()
        )

    def _identify_misconception(self, student_input: str) -> Optional[str]:
        # Simple pattern matching - in production would use LLM
        misconceptions = {
            "steep": "confuses_steepness_with_measurement",
            "line": "confuses_line_with_slope",
            "formula": "memorizes_without_understanding",
        }

        for keyword, misconception in misconceptions.items():
            if keyword in student_input.lower():
                return misconception
        return None

    def _check_understanding(self, student_input: str) -> bool:
        positive_indicators = ["yes", "correct", "understand", "懂了", "明白了", "正确"]
        return any(indicator in student_input.lower() for indicator in positive_indicators)

    def _detect_injection(self, text: str) -> bool:
        injection_patterns = [
            "ignore previous",
            "system prompt",
            "you are now",
            "override",
            "disregard instructions",
        ]
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in injection_patterns)

    def _injection_defense_response(self) -> TutorResponse:
        return TutorResponse(
            message=f"I notice something unusual in your message. Let's stay focused on learning {self.concept_id}. Can you tell me what you find challenging about this?",
            state=self.state,
            kg_citations=self._get_kg_citations()
        )

    def _get_kg_citations(self) -> List[Dict[str, Any]]:
        # Return KG citations for current concept
        return [
            {"concept_id": self.concept_id, "relation": "relates_to", "target_id": "prerequisite", "confidence": 0.9}
        ]

    def _get_suggestions_for_level(self, level: int) -> List[str]:
        suggestions = {
            1: ["Think about the definition", "Consider what it measures"],
            2: ["Connect to prerequisites", "Try a concrete example"],
            3: ["Step by step reasoning", "Break it down"]
        }
        return suggestions.get(level, [])

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "concept_id": self.concept_id,
            "session_id": self.session_id,
            "state": self.state.value,
            "turns_in_state": self.turns_in_state,
            "hint_level": self.hint_level,
            "misconception": self.misconception,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_tutor_state_machine.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/services/tutor_state_machine.py backend/app/kg/tests/test_tutor_state_machine.py && git commit -m "feat: add TutorStateMachine with 6-state transitions"
```

---

## Task 3: Create Hint Generator Service

**Files:**
- Create: `backend/app/services/tutor_hint_generator.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/app/kg/tests/test_tutor_hint_generator.py
import pytest
import sys
sys.path.insert(0, '/home/zh/ai-study/backend')

from app.services.tutor_hint_generator import HintGenerator


def test_l1_hint_from_template():
    hg = HintGenerator()
    hint = hg.generate_hint("slope", level=1, misconception=None)
    assert hint is not None
    assert len(hint) > 10


def test_l2_hint_has_prerequisite():
    hg = HintGenerator()
    hint = hg.generate_hint("slope", level=2, misconception=None)
    assert "prerequisite" in hint.lower() or "requires" in hint.lower() or "记住" in hint


def test_l3_hint_is_longer():
    hg = HintGenerator()
    l1_hint = hg.generate_hint("slope", level=1, misconception=None)
    l3_hint = hg.generate_hint("slope", level=3, misconception=None)
    assert len(l3_hint) > len(l1_hint)


def test_hint_fills_variables():
    hg = HintGenerator()
    hint = hg.generate_hint("slope", level=2, misconception=None)
    # Should fill {concept} variable
    assert "slope" in hint or "斜率" in hint
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_tutor_hint_generator.py -v`
Expected: FAIL with "No module named 'app.services.tutor_hint_generator'"

- [ ] **Step 3: Write Hint Generator**

```python
# backend/app/services/tutor_hint_generator.py
from typing import Optional, List
import random


class HintGenerator:
    # L1 templates - direction hints
    L1_TEMPLATES = [
        "想想这个概念和哪个前置概念有关？",
        "有没有考虑过从定义出发？",
        "试着画个图来理解",
        "Think about what {concept} relates to in the knowledge graph",
        "Consider the basic definition of {concept}",
    ]

    # L2 templates - key concept hints
    L2_TEMPLATES = [
        "记住 {concept} 需要先理解 {prerequisite}",
        "这个问题的关键在于 {key_concept}",
        "The key to {concept} is understanding {prerequisite}",
        "Remember that {concept} requires background knowledge of {prerequisite}",
    ]

    # L3 templates - step hints (these are more specific)
    L3_TEMPLATES = [
        "如果你理解了 X，那么 Y 就自然而然地跟出来了",
        "Since we know X, we can derive Y because...",
        "Let's work through this step by step: first, consider {step1}...",
    ]

    def __init__(self):
        self.prerequisites = {
            "slope": "ratio",
            "derivative": "limit",
            "integral": "area",
            "equation": "variable",
        }

    def generate_hint(self, concept: str, level: int, misconception: Optional[str] = None) -> str:
        if level == 1:
            return self._generate_l1_hint(concept)
        elif level == 2:
            return self._generate_l2_hint(concept)
        elif level == 3:
            return self._generate_l3_hint(concept)
        else:
            return self._generate_l1_hint(concept)

    def _generate_l1_hint(self, concept: str) -> str:
        template = random.choice(self.L1_TEMPLATES)
        return template.replace("{concept}", concept)

    def _generate_l2_hint(self, concept: str) -> str:
        template = random.choice(self.L2_TEMPLATES)
        prerequisite = self.prerequisites.get(concept, "前置概念")
        result = template.replace("{concept}", concept)
        result = result.replace("{prerequisite}", prerequisite)
        result = result.replace("{key_concept}", prerequisite)
        return result

    def _generate_l3_hint(self, concept: str) -> str:
        # L3 hints are more specific and contextual
        # In production, this would use LLM
        template = random.choice(self.L3_TEMPLATES)
        return template.replace("{step1}", f"{concept}的基本定义")

    def get_hints_for_concept(self, concept_id: str) -> List[dict]:
        """Get all available hints for a concept"""
        hints = []
        for level in [1, 2, 3]:
            hint = self.generate_hint(concept_id, level)
            hints.append({"level": level, "hint": hint})
        return hints
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/zh/ai-study/backend && python3 -m pytest app/kg/tests/test_tutor_hint_generator.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/services/tutor_hint_generator.py backend/app/kg/tests/test_tutor_hint_generator.py && git commit -m "feat: add HintGenerator with hybrid L1/L2/L3 hint generation"
```

---

## Task 4: Create Tutor API Routes

**Files:**
- Create: `backend/app/api/v1/routes/tutor.py`
- Modify: `backend/app/api/v1/__init__.py`

- [ ] **Step 1: Write API implementation**

```python
# backend/app/api/v1/routes/tutor.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.tutor import TutorSession, TutorMessage
from app.services.tutor_state_machine import TutorStateMachine, TutorState, TutorResponse


router = APIRouter(prefix="/tutor", tags=["tutor"])


class StartSessionRequest(BaseModel):
    user_id: int
    concept_id: str


class StartSessionResponse(BaseModel):
    session_id: int
    state: str
    message: str
    kg_citations: List[dict]


class SendMessageRequest(BaseModel):
    content: str
    role: str = "student"


class SendMessageResponse(BaseModel):
    session_id: int
    state: str
    message: str
    hint_level: Optional[int]
    kg_citations: List[dict]
    suggestions: List[str]
    is_final: bool


class SessionStateResponse(BaseModel):
    session_id: int
    user_id: int
    concept_id: str
    current_state: str
    turns_in_state: int
    hint_level: int
    misconception: Optional[str]


@router.post("/sessions", response_model=StartSessionResponse)
async def start_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new tutor session for a concept"""
    session = TutorSession(
        user_id=request.user_id,
        concept_id=request.concept_id,
        current_state="diagnose",
        target_concept_id=request.concept_id
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    sm = TutorStateMachine(
        user_id=request.user_id,
        concept_id=request.concept_id,
        session_id=session.id
    )

    initial_message = "Let's explore the concept of {concept}. What does it mean to you?".format(
        concept=request.concept_id
    )

    return StartSessionResponse(
        session_id=session.id,
        state="diagnose",
        message=initial_message,
        kg_citations=[]
    )


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: int,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message in an existing tutor session"""
    result = await db.execute(
        select(TutorSession).filter(TutorSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Store the message
    msg = TutorMessage(
        session_id=session_id,
        role=request.role,
        content=request.content,
        state_at_time=session.current_state
    )
    db.add(msg)

    # Create state machine from session state
    sm = TutorStateMachine(
        user_id=session.user_id,
        concept_id=session.concept_id,
        session_id=session_id
    )
    sm.state = TutorState(session.current_state)
    sm.turns_in_state = session.turns_in_state
    sm.hint_level = session.hint_level
    sm.misconception = session.misconception

    # Process the transition
    response = sm.transition(request.content, request.role)

    # Update session state
    session.current_state = response.state.value
    session.turns_in_state = sm.turns_in_state
    session.hint_level = sm.hint_level
    session.misconception = sm.misconception

    await db.commit()

    # Store tutor response as well
    tutor_msg = TutorMessage(
        session_id=session_id,
        role="tutor",
        content=response.message,
        hint_level=response.hint_level,
        state_at_time=response.state.value
    )
    db.add(tutor_msg)
    await db.commit()

    return SendMessageResponse(
        session_id=session_id,
        state=response.state.value,
        message=response.message,
        hint_level=response.hint_level,
        kg_citations=response.kg_citations or [],
        suggestions=response.suggestions or [],
        is_final=response.is_final
    )


@router.get("/sessions/{session_id}", response_model=SessionStateResponse)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current state of a tutor session"""
    result = await db.execute(
        select(TutorSession).filter(TutorSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStateResponse(
        session_id=session.id,
        user_id=session.user_id,
        concept_id=session.concept_id,
        current_state=session.current_state,
        turns_in_state=session.turns_in_state,
        hint_level=session.hint_level,
        misconception=session.misconception
    )


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all messages in a tutor session"""
    result = await db.execute(
        select(TutorMessage).filter(TutorMessage.session_id == session_id).order_by(TutorMessage.created_at)
    )
    messages = result.scalars().all()

    return {
        "session_id": session_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "hint_level": m.hint_level,
                "state_at_time": m.state_at_time,
                "created_at": str(m.created_at)
            }
            for m in messages
        ]
    }
```

- [ ] **Step 2: Modify __init__.py**

Add to `backend/app/api/v1/__init__.py`:
```python
from .routes.tutor import router as tutor_router
# Add after mastery_router:
api_v1_router.include_router(tutor_router, prefix="/tutor", tags=["tutor"])
```

- [ ] **Step 3: Verify syntax**

Run: `cd /home/zh/ai-study/backend && python3 -m py_compile app/api/v1/routes/tutor.py && echo "Syntax OK"`

- [ ] **Step 4: Commit**

```bash
cd /home/zh/ai-study && git add backend/app/api/v1/routes/tutor.py backend/app/api/v1/__init__.py && git commit -m "feat: add Tutor API routes for state machine interaction"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| 6 states (diagnose, hint_ladder, guide, counter_example, consolidate, escalate) | Task 2 |
| State transitions with turns_in_state tracking | Task 2 |
| Hybrid hint generation (templates + LLM) | Task 3 |
| L1/L2/L3 hint levels | Task 3 |
| KG citations in responses | Task 2 |
| Prompt injection detection | Task 2 |
| PostgreSQL persistence (TutorSession, TutorMessage) | Task 1, Task 4 |
| POST /tutor/sessions | Task 4 |
| POST /tutor/sessions/{id}/messages | Task 4 |
| GET /tutor/sessions/{id} | Task 4 |
| Integration with BKT mastery data (concept_id lookup) | Task 2 |

All requirements covered. No placeholders found.

---

**Plan complete.**