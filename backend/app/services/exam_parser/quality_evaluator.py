"""Quality evaluation for exam extraction results."""

from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class ExtractionQuality:
    """Quality metrics for extraction results."""
    total_questions: int
    type_distribution: Dict[str, int]
    unknown_type_count: int
    questions_with_options: int
    questions_with_material: int
    average_length: float
    score: float  # 0-100
    issues: List[str]


def evaluate_extraction(questions: List[Any]) -> ExtractionQuality:
    """Evaluate the quality of extracted questions.

    Args:
        questions: List of Question objects from exam_parser

    Returns:
        ExtractionQuality with metrics and issues
    """
    if not questions:
        return ExtractionQuality(
            total_questions=0,
            type_distribution={},
            unknown_type_count=0,
            questions_with_options=0,
            questions_with_material=0,
            average_length=0.0,
            score=0.0,
            issues=["No questions extracted"]
        )

    issues = []
    type_dist = {}
    unknown_count = 0
    with_options = 0
    with_material = 0
    total_length = 0

    for q in questions:
        qtype = getattr(q, '题型', '未知')
        type_dist[qtype] = type_dist.get(qtype, 0) + 1

        if qtype == '未知':
            unknown_count += 1

        # Check for options (presence of multi-line content with patterns)
        content = getattr(q, '内容', '') or ''
        if '\n' in content and len(content) > 50:
            with_options += 1

        # Check for material
        material = getattr(q, '材料', '') or ''
        if material and len(material) > 5:
            with_material += 1

        total_length += len(content)

    # Calculate score
    score = 100.0

    # Penalty for unknown types
    if unknown_count > 0:
        unknown_ratio = unknown_count / len(questions)
        score -= unknown_ratio * 30
        issues.append(f"{unknown_count} questions with unknown type ({unknown_ratio:.1%})")

    # Penalty for very short questions
    avg_length = total_length / len(questions) if questions else 0
    if avg_length < 20:
        score -= 20
        issues.append(f"Average question length too short: {avg_length:.1f} chars")

    # Bonus for good type distribution
    known_types = len([t for t in type_dist.keys() if t != '未知'])
    if known_types >= 3:
        score += 5

    # Bonus for options
    if with_options > len(questions) * 0.5:
        score += 5

    # Bonus for materials
    if with_material > 0:
        score += 5

    score = max(0.0, min(100.0, score))

    return ExtractionQuality(
        total_questions=len(questions),
        type_distribution=type_dist,
        unknown_type_count=unknown_count,
        questions_with_options=with_options,
        questions_with_material=with_material,
        average_length=avg_length,
        score=score,
        issues=issues
    )


def get_quality_report(quality: ExtractionQuality) -> str:
    """Generate a human-readable quality report."""
    lines = [
        "=== Extraction Quality Report ===",
        f"Total Questions: {quality.total_questions}",
        f"Quality Score: {quality.score:.1f}/100",
        "",
        "Type Distribution:",
    ]

    for qtype, count in sorted(quality.type_distribution.items()):
        lines.append(f"  {qtype}: {count}")

    lines.extend([
        "",
        f"Questions with options: {quality.questions_with_options}",
        f"Questions with material: {quality.questions_with_material}",
        f"Average length: {quality.average_length:.1f} chars",
    ])

    if quality.issues:
        lines.append("")
        lines.append("Issues:")
        for issue in quality.issues:
            lines.append(f"  - {issue}")

    return "\n".join(lines)