"""Extract questions tool using LLM."""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

MAX_MARKDOWN_LENGTH = 4000

EXTRACTION_PROMPT = """你是试题解析专家。从以下试卷内容中提取题目，以JSON数组返回。

{page_context}

试卷内容:
{markdown}

输出格式 (JSON数组):
[
  {{
    "题型": "单选题/多选题/判断题/填空题/主观题/未知",
    "内容": "题目完整文本(包含选项)",
    "选项": ["A选项内容", "B选项内容", ...]或null,
    "材料": "关联材料文本或null",
    "答案": "识别到的答案或null",
    "置信度": 0.0-1.0,
    "页码": 数字或null,
    "问题": ["解析问题描述"]或[]
  }}
]

规则:
- 只返回JSON数组，不要其他内容
- 无法解析的题目也要返回，置信度设为0
- 选项应为完整文本，不要截断
- 材料题要将材料单独提取"""


def extract_questions_tool(markdown: str, page_context: str = "") -> Dict[str, Any]:
    """Use LLM to extract questions from markdown.

    Args:
        markdown: The markdown content to parse
        page_context: Additional context about the page

    Returns:
        Dict with 'success', 'questions', and optional 'error'
    """
    from app.kg.src.llm_router import LLMRouter

    truncated = len(markdown) > MAX_MARKDOWN_LENGTH
    prompt = EXTRACTION_PROMPT.format(
        page_context=page_context,
        markdown=markdown[:MAX_MARKDOWN_LENGTH]
    )

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

        questions = json.loads(content)
        logger.info(f"LLM extracted {len(questions)} questions")

        return {
            "success": True,
            "questions": questions if isinstance(questions, list) else [],
            "count": len(questions) if isinstance(questions, list) else 0,
            "truncated": truncated,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        return {"success": False, "error": f"JSON decode error: {e}", "questions": [], "count": 0, "truncated": truncated}
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return {"success": False, "error": str(e), "questions": [], "count": 0, "truncated": truncated}
