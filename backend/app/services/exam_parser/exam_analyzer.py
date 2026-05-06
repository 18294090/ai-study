"""LLM-assisted question type detection and content analysis."""

import json
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class QuestionAnalysis(BaseModel):
    """Analysis result for a single question."""
    original_text: str
    detected_type: str
    confidence: float
    has_answer: bool
    answer_format: Optional[str] = None
    has_material: bool
    material_text: Optional[str] = None
    options: List[str] = []
    reasoning: str


class ExamAnalyzer:
    """Use LLM to analyze exam text and extract structured question information."""

    def __init__(self):
        self.llm_router = None

    def _get_llm_client(self):
        if self.llm_router is None:
            from app.kg.src.llm_router import LLMRouter
            self.llm_router = LLMRouter()
        return self.llm_router.get_client()

    def analyze_question(self, text: str) -> QuestionAnalysis:
        """Analyze a single question text using LLM."""
        prompt = f"""分析以下题目文本，提取结构化信息。

题目文本:
{text[:1000]}

请以JSON格式返回分析结果:
{{
    "detected_type": "单选题/多选题/判断题/填空题/主观题/未知",
    "confidence": 0.0-1.0,
    "has_answer": true/false,
    "answer_format": "single/multiple/text/empty",
    "has_material": true/false,
    "material_text": "材料内容或null",
    "options": ["选项A", "选项B", ...]或[],
    "reasoning": "分析理由"
}}

只返回一个JSON对象，不要有其他内容。"""

        try:
            client = self._get_llm_client()
            response = client.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            data = json.loads(content.strip())
            return QuestionAnalysis(
                original_text=text,
                detected_type=data.get("detected_type", "未知"),
                confidence=float(data.get("confidence", 0.5)),
                has_answer=data.get("has_answer", False),
                answer_format=data.get("answer_format"),
                has_material=data.get("has_material", False),
                material_text=data.get("material_text"),
                options=data.get("options", []),
                reasoning=data.get("reasoning", "")
            )
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}, falling back to rule-based")
            return QuestionAnalysis(
                original_text=text,
                detected_type="未知",
                confidence=0.0,
                has_answer=False,
                has_material=False,
                reasoning=f"LLM failed: {e}"
            )

    def analyze_batch(self, texts: List[str]) -> List[QuestionAnalysis]:
        """Analyze multiple questions in batch."""
        results = []
        for text in texts:
            result = self.analyze_question(text)
            results.append(result)
        return results


def rule_based_type_detection(text: str, options: List[str] = None) -> tuple[str, float]:
    """Fallback rule-based question type detection.

    Returns:
        Tuple of (question_type, confidence)
    """
    text = text.strip()
    options = options or []

    # Multi-choice hints
    if any(kw in text for kw in ["多选", "(多选)", "【多选】", "[多选]"]):
        return "多选题", 0.9
    if any(kw in text for kw in ["判断题", "对错", "是非", "正确", "错误"]):
        return "判断题", 0.85

    # Option-based detection
    if len(options) >= 2:
        opt_text = "\n".join(options)
        # Check for single letter options (A, B, C, D)
        if all(
            len(o.strip()) > 0 and (o.strip()[0].upper() in "ABCDEFGH" or o.strip()[0] in "①②③④")
            for o in options if o.strip()
        ):
            # Check for multi-choice patterns in options
            if any(kw in opt_text for kw in ["以上都是", "以上都不", "ABC", "AB", "BCD"]):
                return "多选题", 0.75
            return "单选题", 0.8

    # Keyword-based detection
    if any(kw in text for kw in ["简答", "简述", "问答", "论述"]):
        return "主观题", 0.8
    if any(kw in text for kw in ["填空", "填写", "完成"]):
        return "填空题", 0.75

    return "未知", 0.3