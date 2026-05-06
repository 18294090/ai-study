"""Tools for the exam extraction agent."""

import json
import logging
from typing import List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_pdf_tool(file_path: str) -> Tuple[str, List[dict]]:
    """Parse PDF using MinerU and return markdown and images.

    Returns:
        Tuple of (markdown, images_info)
    """
    try:
        from mineru import MagicPDF

        client = MagicPDF(device="cpu")
        pdf_bytes = Path(file_path).read_bytes()
        result = client.parse(pdf_bytes, parse_method="full")

        markdown = result.get("markdown", "")
        images_info = result.get("images", []) or []

        logger.info(f"Parsed PDF with {len(markdown)} chars, {len(images_info)} images")
        return markdown, images_info

    except ImportError:
        logger.error("MinerU not installed")
        return "", []
    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")
        return "", []


def extract_questions_llm(markdown: str, page_context: str = "") -> List[dict]:
    """Use LLM to extract questions from markdown.

    Args:
        markdown: The markdown content to parse
        page_context: Additional context about the page

    Returns:
        List of extracted question dictionaries
    """
    from app.kg.src.llm_router import LLMRouter

    prompt = f"""你是试题解析专家。从以下试卷内容中提取题目，以JSON数组返回。

{page_context}

试卷内容:
{markdown[:4000]}

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

    try:
        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)

        content = response.content if hasattr(response, 'content') else str(response)

        # Extract JSON from response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        questions = json.loads(content)
        logger.info(f"LLM extracted {len(questions)} questions")
        return questions if isinstance(questions, list) else []

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return []


def validate_question(question: dict) -> Tuple[bool, List[str]]:
    """Validate a single extracted question.

    Returns:
        Tuple of (is_valid, issues)
    """
    issues = []

    # Check content
    content = question.get("内容", "")
    if not content or len(content) < 5:
        issues.append("题目内容过短或为空")

    # Check type
    qtype = question.get("题型", "未知")
    valid_types = ["单选题", "多选题", "判断题", "填空题", "主观题", "未知"]
    if qtype not in valid_types:
        issues.append(f"题型 '{qtype}' 不在标准类型中")

    # Check options for choice questions
    if qtype in ["单选题", "多选题"]:
        options = question.get("选项", [])
        if not options or len(options) < 2:
            issues.append("选择题缺少选项")
        # Check for proper option format
        for i, opt in enumerate(options):
            if len(opt) < 1:
                issues.append(f"选项 {i+1} 内容为空")

    # Check confidence
    confidence = question.get("置信度", 0.0)
    if confidence < 0.5 and qtype == "未知":
        issues.append("置信度过低且题型未知")

    is_valid = len(issues) == 0
    return is_valid, issues


def refine_question_llm(question: dict) -> dict:
    """Use LLM to refine a low-confidence question.

    Args:
        question: The question dict to refine

    Returns:
        Refined question dict
    """
    from app.kg.src.llm_router import LLMRouter

    prompt = f"""你是试题解析专家。分析以下题目，尝试改进解析结果。

原始题目:
{json.dumps(question, ensure_ascii=False, indent=2)}

请以JSON格式返回改进后的题目:
{{
    "题型": "单选题/多选题/判断题/填空题/主观题/未知",
    "内容": "改进后的题目文本",
    "选项": ["A选项", "B选项", ...]或null,
    "材料": "关联材料或null",
    "答案": "答案或null",
    "置信度": 0.0-1.0,
    "问题": ["仍存在的问题"]或[]
}}

如果无法改进，置信度设为0，问题描述原因。"""

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
        logger.info(f"Refined question {question.get('id')}: confidence {question.get('置信度')} -> {refined.get('置信度')}")
        return refined

    except Exception as e:
        logger.error(f"Failed to refine question: {e}")
        return question


def split_pages(markdown: str) -> List[str]:
    """Split markdown by pages (using page markers or simple heuristics).

    Args:
        markdown: Full markdown content

    Returns:
        List of page markdown strings
    """
    # MinerU marks pages with "page N" or similar markers
    import re

    # Try to split by page markers
    page_markers = [
        r'\n--- page \d+ ---\n',
        r'\nPage \d+\n',
        r'\n# Page \d+\n',
        r'\[\[PAGE \d+\]\]',
    ]

    pages = []
    last_end = 0

    for marker in page_markers:
        matches = list(re.finditer(marker, markdown, re.IGNORECASE))
        if matches:
            for m in matches:
                pages.append(markdown[last_end:m.start()])
                last_end = m.end()
            if last_end < len(markdown):
                pages.append(markdown[last_end:])
            return [p for p in pages if p.strip()]

    # Fallback: split by headings or sections
    # Just return as single page if no markers found
    return [markdown] if markdown.strip() else []


def detect_answer_key(markdown: str) -> List[dict]:
    """Detect potential answer keys in the content.

    Args:
        markdown: Content to search

    Returns:
        List of potential answer entries
    """
    from app.kg.src.llm_router import LLMRouter

    prompt = f"""分析以下内容，识别答案区域。

内容:
{markdown[:3000]}

请以JSON数组格式返回发现的答案:
[
  {{
    "答案位置": "描述答案所在位置",
    "答案内容": "如 A, B, C, 正确, 错误 等",
    "页码": 数字或null
  }}
]

如果没有发现答案，返回空数组 []。只返回JSON。"""

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

        answers = json.loads(content)
        return answers if isinstance(answers, list) else []

    except Exception as e:
        logger.error(f"Failed to detect answers: {e}")
        return []