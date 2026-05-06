"""Refine question tool using LLM."""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

REFINE_PROMPT = """你是试题解析专家。分析以下题目，尝试改进解析结果。

原始题目:
{question_json}

请以JSON格式返回改进后的题目:
{{
    "题型": "...",
    "内容": "...",
    "选项": [...],
    "材料": "...",
    "答案": "...",
    "置信度": 0.0-1.0,
    "问题": []
}}

只返回一个JSON对象，不要其他内容。"""


def refine_question_tool(question: Dict[str, Any]) -> Dict[str, Any]:
    """Use LLM to refine a low-confidence question.

    Args:
        question: The question dict to refine

    Returns:
        Dict with 'success', 'refined_question', and optional 'error'
    """
    from app.kg.src.llm_router import LLMRouter

    prompt = REFINE_PROMPT.format(question_json=json.dumps(question, ensure_ascii=False, indent=2))

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)

        content = response.content if hasattr(response, 'content') else str(response)

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        refined = json.loads(content)
        logger.info(f"Refined question id={question.get('id')}")

        return {
            "success": True,
            "refined_question": refined,
            "original_confidence": question.get("置信度", 0),
            "refined_confidence": refined.get("置信度", 0),
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse refined question as JSON: {e}")
        return {"success": False, "error": f"JSON decode error: {e}", "refined_question": question}
    except Exception as e:
        logger.error(f"LLM refinement failed: {e}")
        return {"success": False, "error": str(e), "refined_question": question}