from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


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


class HintGenerator:
    L1_TEMPLATES = [
        "想想这个概念和哪个前置概念有关？",
        "有没有考虑过从定义出发？",
        "试着画个图来理解",
    ]

    L2_TEMPLATES = [
        "记住 {concept} 需要先理解 {prerequisite}",
        "这个问题的关键在于 {key_concept}",
    ]

    L3_TEMPLATES = [
        "如果你理解了 X，那么 Y 就自然而然地跟出来了",
        "Since we know X, we can derive Y because...",
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
            template = self.L1_TEMPLATES[0]
            return template.replace("{concept}", concept)
        elif level == 2:
            template = self.L2_TEMPLATES[0]
            prereq = self.prerequisites.get(concept, "前置概念")
            return template.replace("{concept}", concept).replace("{prerequisite}", prereq)
        else:
            template = self.L3_TEMPLATES[0]
            return template.replace("{step1}", f"{concept}的基本定义")


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

        if self._detect_injection(student_input):
            return self._injection_defense_response()

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
            return TutorResponse(
                message="Interesting. Can you tell me more about your understanding?",
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

    def _tutor_response(self, message: str) -> TutorResponse:
        return TutorResponse(
            message=message,
            state=self.state,
            kg_citations=self._get_kg_citations()
        )

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