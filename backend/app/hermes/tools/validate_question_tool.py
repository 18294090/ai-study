"""Validate question tool."""

import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

VALID_TYPES = ["单选题", "多选题", "判断题", "填空题", "主观题", "未知"]


def validate_question_tool(question: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single extracted question.

    Args:
        question: The question dict to validate

    Returns:
        Dict with 'is_valid', 'issues', and 'confidence'
    """
    issues = []

    content = question.get("内容", "")
    if not content or len(content) < 5:
        issues.append("题目内容过短或为空")

    qtype = question.get("题型", "未知")
    if qtype not in VALID_TYPES:
        issues.append(f"题型 '{qtype}' 不在标准类型中")

    if qtype in ["单选题", "多选题"]:
        options = question.get("选项", [])
        if not options or len(options) < 2:
            issues.append("选择题缺少选项")
        for i, opt in enumerate(options):
            if len(opt) < 1:
                issues.append(f"选项 {i+1} 内容为空")

    confidence = question.get("置信度", 0.0)
    if confidence < 0.5 and qtype == "未知":
        issues.append("置信度过低且题型未知")

    is_valid = len(issues) == 0

    return {
        "is_valid": is_valid,
        "issues": issues,
        "confidence": confidence,
        "question_id": question.get("id"),
    }