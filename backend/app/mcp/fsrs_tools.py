from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

from app.mcp.kg_tools import ToolResponse


def fsrs_calculate_intervals(stability: float, difficulty: float, rating: int) -> tuple:
    new_stability = stability * (1 + 0.1 * (5 - rating))
    new_difficulty = difficulty + 0.1 * (rating - 3)
    new_difficulty = max(0.1, min(5.0, new_difficulty))
    retention = 0.9 ** (1 / (stability * (1 + 0.1 * (rating - 3))))
    interval = stability * (1 + 0.1 * (rating - 3))
    interval = max(1, interval)
    return new_stability, new_difficulty, interval, retention


async def fsrs_create_card(user_id: int, concept_id: int,
                           initial_stability: Optional[float],
                           initial_difficulty: Optional[float],
                           agent_id: str, session_id: str) -> ToolResponse:
    """Create FSRS flashcard"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.fsrs import FSRSCard
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            stability = initial_stability if initial_stability is not None else 0.0
            difficulty = initial_difficulty if initial_difficulty is not None else 0.3

            card = FSRSCard(
                user_id=user_id,
                concept_id=concept_id,
                state="new",
                stability=stability,
                difficulty=difficulty,
                reps=0,
            )
            db.add(card)
            db.commit()
            db.refresh(card)

            return ToolResponse(
                success=True,
                data={
                    "card_id": card.id,
                    "user_id": user_id,
                    "concept_id": concept_id,
                    "state": card.state,
                    "stability": card.stability,
                    "difficulty": card.difficulty,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"fsrs_create_card failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def fsrs_review(card_id: int, rating: int, response_time: float,
                      agent_id: str, session_id: str) -> ToolResponse:
    """Submit FSRS review"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.fsrs import FSRSCard, FSRSReviewLog
        from app.db.session import SessionLocal
        from datetime import timedelta

        db = SessionLocal()
        try:
            card = db.query(FSRSCard).filter(FSRSCard.id == card_id).first()
            if not card:
                return ToolResponse(
                    success=False,
                    error=f"Card {card_id} not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            new_stability, new_difficulty, new_interval, retention = fsrs_calculate_intervals(
                card.stability, card.difficulty, rating
            )

            card.stability = new_stability
            card.difficulty = new_difficulty
            card.interval = new_interval
            card.last_result = "correct" if rating >= 3 else "incorrect"
            card.reps += 1
            card.due = datetime.utcnow() + timedelta(days=new_interval)
            card.last_review = datetime.utcnow()
            if rating == 1:
                card.lapses += 1
            if card.state == "new":
                card.state = "learning" if rating < 3 else "review"

            review_log = FSRSReviewLog(
                card_id=card_id,
                user_id=card.user_id,
                reviewed_at=datetime.utcnow(),
                rating=rating,
                response_time=response_time,
                stability_delta=new_stability - card.stability,
                new_interval=new_interval,
                new_stability=new_stability,
                retention=retention,
            )
            db.add(review_log)
            db.commit()

            return ToolResponse(
                success=True,
                data={
                    "card_id": card.id,
                    "new_stability": new_stability,
                    "new_difficulty": new_difficulty,
                    "new_interval": new_interval,
                    "retention": retention,
                    "reps": card.reps,
                    "state": card.state,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"fsrs_review failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def fsrs_get_due(user_id: int, limit: int, agent_id: str, session_id: str) -> ToolResponse:
    """Get due FSRS cards"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.fsrs import FSRSCard
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            now = datetime.utcnow()
            cards = db.query(FSRSCard).filter(
                FSRSCard.user_id == user_id,
                FSRSCard.due <= now,
            ).order_by(FSRSCard.due).limit(limit).all()

            return ToolResponse(
                success=True,
                data={
                    "cards": [
                        {
                            "card_id": c.id,
                            "concept_id": c.concept_id,
                            "state": c.state,
                            "due": c.due.isoformat() if c.due else None,
                            "stability": c.stability,
                            "difficulty": c.difficulty,
                            "reps": c.reps,
                            "lapses": c.lapses,
                        }
                        for c in cards
                    ],
                    "count": len(cards),
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"fsrs_get_due failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def fsrs_get_stats(user_id: int, agent_id: str, session_id: str) -> ToolResponse:
    """Get FSRS statistics"""
    operation_id = str(uuid.uuid4())
    try:
        from app.models.fsrs import FSRSCard, FSRSReviewLog
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            total_cards = db.query(FSRSCard).filter(FSRSCard.user_id == user_id).count()
            new_cards = db.query(FSRSCard).filter(
                FSRSCard.user_id == user_id,
                FSRSCard.state == "new"
            ).count()
            learning_cards = db.query(FSRSCard).filter(
                FSRSCard.user_id == user_id,
                FSRSCard.state == "learning"
            ).count()
            review_cards = db.query(FSRSCard).filter(
                FSRSCard.user_id == user_id,
                FSRSCard.state == "review"
            ).count()

            total_reviews = db.query(FSRSReviewLog).filter(
                FSRSReviewLog.user_id == user_id
            ).count()

            recent_reviews = db.query(FSRSReviewLog).filter(
                FSRSReviewLog.user_id == user_id
            ).order_by(FSRSReviewLog.reviewed_at.desc()).limit(100).all()

            avg_retention = sum(r.retention for r in recent_reviews) / len(recent_reviews) if recent_reviews else 0

            return ToolResponse(
                success=True,
                data={
                    "user_id": user_id,
                    "total_cards": total_cards,
                    "new_cards": new_cards,
                    "learning_cards": learning_cards,
                    "review_cards": review_cards,
                    "total_reviews": total_reviews,
                    "avg_retention": avg_retention,
                },
                operation_id=operation_id,
                timestamp=datetime.utcnow(),
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"fsrs_get_stats failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )