"""Exam extraction agent using LangGraph."""

import logging
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from .state import ExamAgentState, ExtractedQuestion, initial_state, ExtractionStatus
from .tools import (
    parse_pdf_tool,
    extract_questions_llm,
    validate_question,
    refine_question_llm,
    split_pages,
    detect_answer_key,
)

logger = logging.getLogger(__name__)


def parse_node(state: ExamAgentState) -> ExamAgentState:
    """Parse the PDF file using MinerU."""
    logger.info(f"Parsing PDF: {state['file_path']}")

    markdown, images_info = parse_pdf_tool(state["file_path"])

    if not markdown:
        state["status"] = ExtractionStatus.FAILED.value
        state["errors"].append("Failed to parse PDF or empty content")
        return state

    state["raw_markdown"] = markdown
    state["status"] = ExtractionStatus.IN_PROGRESS.value

    # Split into pages
    pages = split_pages(markdown)
    from .state import PageContext
    state["pages"] = [
        PageContext(page_num=i+1, markdown=page)
        for i, page in enumerate(pages)
    ]
    state["total_pages"] = len(pages)

    logger.info(f"Split into {len(pages)} pages")
    return state


def extract_page_node(state: ExamAgentState) -> ExamAgentState:
    """Extract questions from the current page using LLM."""
    current_page = state["current_page"]

    if current_page >= state["total_pages"]:
        return state

    page = state["pages"][current_page]

    logger.info(f"Extracting questions from page {current_page + 1}/{state['total_pages']}")

    # Detect answers on this page first
    answers = detect_answer_key(page.markdown)
    if answers:
        state["pending_answers"].extend([a.get("答案内容") for a in answers if a.get("答案内容")])

    # Extract questions using LLM
    questions = extract_questions_llm(page.markdown, f"Page {current_page + 1} of {state['total_pages']}")

    # Process and validate each question
    for i, q in enumerate(questions):
        q_id = state["last_question_id"] + i + 1
        q["id"] = q_id

        # Validate
        is_valid, issues = validate_question(q)

        if not is_valid and q.get("置信度", 0) < 0.5:
            # Try to refine
            refined = refine_question_llm(q)
            if refined.get("置信度", 0) > q.get("置信度", 0):
                q = refined
                issues = q.get("问题", [])

        q["问题"] = issues

        # Track low confidence questions
        if q.get("置信度", 0) < state["confidence_threshold"]:
            state["low_confidence_questions"].append(q_id)

        state["questions"].append(q)
        page.questions_found.append(q_id)

    state["last_question_id"] = state["last_question_id"] + len(questions)

    # Move to next page
    state["current_page"] = current_page + 1

    return state


def should_continue_extraction(state: ExamAgentState) -> str:
    """Determine if we should continue extraction or refine results."""
    if state["current_page"] >= state["total_pages"]:
        if state["low_confidence_questions"]:
            return "refine"
        return "finalize"
    return "extract"


def refine_node(state: ExamAgentState) -> ExamAgentState:
    """Refine low-confidence questions."""
    if not state["low_confidence_questions"]:
        return state

    logger.info(f"Refining {len(state['low_confidence_questions'])} low-confidence questions")

    for q_id in state["low_confidence_questions"]:
        for q in state["questions"]:
            if q.get("id") == q_id and q.get("置信度", 0) < state["confidence_threshold"]:
                refined = refine_question_llm(q)
                # Update in place
                for key in refined:
                    q[key] = refined[key]

                if refined.get("置信度", 0) >= state["confidence_threshold"]:
                    state["low_confidence_questions"].remove(q_id)

    state["refinement_needed"] = False
    return state


def finalize_node(state: ExamAgentState) -> ExamAgentState:
    """Finalize extraction and generate report."""
    total = len(state["questions"])
    low_conf = len(state["low_confidence_questions"])

    state["status"] = ExtractionStatus.COMPLETED.value

    state["extraction_report"] = {
        "total_questions": total,
        "pages_processed": state["total_pages"],
        "high_confidence": total - low_conf,
        "low_confidence": low_conf,
        "confidence_threshold": state["confidence_threshold"],
        "pending_answers": len(state["pending_answers"]),
        "errors": state["errors"],
    }

    logger.info(f"Extraction complete: {total} questions, {low_conf} low confidence")

    return state


def build_exam_agent() -> StateGraph:
    """Build the exam extraction agent graph."""

    g = StateGraph(ExamAgentState)

    # Add nodes
    g.add_node("parse", parse_node)
    g.add_node("extract", extract_page_node)
    g.add_node("refine", refine_node)
    g.add_node("finalize", finalize_node)

    # Set entry point
    g.set_entry_point("parse")

    # Graph flow
    g.add_edge("parse", "extract")

    # Conditional loop for page extraction
    g.add_conditional_edges(
        "extract",
        should_continue_extraction,
        {
            "extract": "extract",  # Continue to next page
            "refine": "refine",   # All pages done, refine low confidence
            "finalize": "finalize"  # No refinement needed
        }
    )

    g.add_edge("refine", "finalize")
    g.add_edge("finalize", END)

    return g.compile()


# Global agent instance
_exam_agent = None


def get_exam_agent():
    """Get or create the exam agent instance."""
    global _exam_agent
    if _exam_agent is None:
        _exam_agent = build_exam_agent()
    return _exam_agent


async def run_exam_agent(file_path: str, source: str = "", confidence_threshold: float = 0.6) -> Dict[str, Any]:
    """Run the exam extraction agent.

    Args:
        file_path: Path to the PDF file
        source: Source identifier (e.g., filename)
        confidence_threshold: Minimum confidence for accepted questions

    Returns:
        Dictionary with questions and extraction report
    """
    state = initial_state(file_path, source)
    state["confidence_threshold"] = confidence_threshold

    agent = get_exam_agent()

    result = await agent.ainvoke(state)

    return {
        "questions": result.get("questions", []),
        "report": result.get("extraction_report", {}),
        "status": result.get("status", "unknown"),
    }


# Synchronous version for backwards compatibility
def run_exam_agent_sync(file_path: str, source: str = "", confidence_threshold: float = 0.6) -> Dict[str, Any]:
    """Synchronous version of run_exam_agent."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(run_exam_agent(file_path, source, confidence_threshold))