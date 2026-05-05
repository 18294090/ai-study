from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.fsrs import FSRSCard, FSRSReviewLog, CardState, ReviewRating
from app.services.fsrs_scheduler import FSRSScheduler, FSRSOptimizer, ScheduleResult

router = APIRouter(prefix="/fsrs", tags=["fsrs"])


class CreateCardRequest(BaseModel):
    user_id: int
    concept_id: int
    initial_stability: Optional[float] = None
    initial_difficulty: Optional[float] = None


class CardResponse(BaseModel):
    card_id: int
    user_id: int
    concept_id: int
    state: str
    stability: float
    interval: float
    due: datetime


class ReviewRequest(BaseModel):
    card_id: int
    rating: int
    response_time: float


class ReviewResponse(BaseModel):
    card_id: int
    next_interval: float
    next_due: datetime
    stability: float
    retrievability: float


class DueCardResponse(BaseModel):
    card_id: int
    concept_id: int
    state: str
    due: datetime
    interval: float
    stability: float


class DueResponse(BaseModel):
    cards: List[DueCardResponse]
    total_due: int


class StatsResponse(BaseModel):
    user_id: int
    total_cards: int
    cards_by_state: dict
    average_stability: float
    average_interval: float


scheduler = FSRSScheduler()


def _compute_retrievability(stability: float, elapsed_days: float) -> float:
    """计算可回忆性 R(t) = exp((t - s) / (-9))"""
    import math
    if stability <= 0:
        return 0.0
    return math.exp(-elapsed_days / stability)


def _card_to_dataclass(card: FSRSCard) -> "FSRSCard":
    """Convert ORM model to scheduler dataclass"""
    from app.services.fsrs_scheduler import FSRSCard as SchedulerCard
    return SchedulerCard(
        id=card.id,
        user_id=card.user_id,
        concept_id=card.concept_id,
        stability=card.stability,
        difficulty=card.difficulty,
        state=card.state,
        lapses=card.lapses,
        reps=card.reps,
        due=card.due or datetime.utcnow(),
        last_review=card.last_review
    )


@router.post("/cards", response_model=CardResponse, status_code=201)
async def create_card(
    request: CreateCardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stability = request.initial_stability if request.initial_stability is not None else 0.5
    difficulty = request.initial_difficulty if request.initial_difficulty is not None else 2.5

    card = FSRSCard(
        user_id=request.user_id,
        concept_id=request.concept_id,
        state=CardState.NEW.value,
        stability=stability,
        difficulty=difficulty,
        interval=0.0,
        due=datetime.now(timezone.utc),
        reps=0,
        lapses=0
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)

    return CardResponse(
        card_id=card.id,
        user_id=card.user_id,
        concept_id=card.concept_id,
        state=card.state,
        stability=card.stability,
        interval=card.interval,
        due=card.due
    )


@router.post("/review", response_model=ReviewResponse)
async def review_card(
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if request.rating < 1 or request.rating > 4:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 4")

    result = await db.execute(
        select(FSRSCard).filter(FSRSCard.id == request.card_id)
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    scheduler_card = _card_to_dataclass(card)
    schedule_result = scheduler.schedule(scheduler_card, request.rating)

    now = datetime.now(timezone.utc)
    elapsed_days = 0.0
    if card.last_review:
        elapsed_days = (now - card.last_review).total_seconds() / 86400

    old_retrievability = _compute_retrievability(card.stability, elapsed_days) if card.stability > 0 else 0.0

    card.stability = schedule_result.next_stability
    card.difficulty = schedule_result.next_difficulty
    card.interval = schedule_result.next_interval
    card.due = schedule_result.due
    card.last_review = now
    card.last_result = {1: "again", 2: "hard", 3: "good", 4: "easy"}.get(request.rating)
    card.reps += 1
    if request.rating == 1:
        card.lapses += 1

    new_retrievability = 0.9

    log = FSRSReviewLog(
        card_id=card.id,
        user_id=card.user_id,
        reviewed_at=now,
        rating=request.rating,
        response_time=request.response_time,
        stability_delta=schedule_result.next_stability - scheduler_card.stability,
        new_interval=schedule_result.next_interval,
        new_stability=schedule_result.next_stability,
        retention=new_retrievability
    )
    db.add(log)
    await db.commit()
    await db.refresh(card)

    return ReviewResponse(
        card_id=card.id,
        next_interval=schedule_result.next_interval,
        next_due=schedule_result.due,
        stability=schedule_result.next_stability,
        retrievability=new_retrievability
    )


@router.get("/due/{user_id}", response_model=DueResponse)
async def get_due_cards(
    user_id: int,
    limit: int = 20,
    concept_ids: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)

    stmt = select(FSRSCard).filter(
        FSRSCard.user_id == user_id,
        FSRSCard.due <= now
    )

    if concept_ids:
        concept_id_list = [int(x) for x in concept_ids.split(",")]
        stmt = stmt.filter(FSRSCard.concept_id.in_(concept_id_list))

    stmt = stmt.order_by(FSRSCard.due.asc()).limit(limit)
    result = await db.execute(stmt)
    cards = result.scalars().all()

    due_cards = [
        DueCardResponse(
            card_id=c.id,
            concept_id=c.concept_id,
            state=c.state,
            due=c.due,
            interval=c.interval,
            stability=c.stability
        )
        for c in cards
    ]

    count_stmt = select(func.count(FSRSCard.id)).filter(
        FSRSCard.user_id == user_id,
        FSRSCard.due <= now
    )
    total_result = await db.execute(count_stmt)
    total_due = total_result.scalar() or 0

    return DueResponse(cards=due_cards, total_due=total_due)


@router.get("/stats/{user_id}", response_model=StatsResponse)
async def get_stats(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(FSRSCard).filter(FSRSCard.user_id == user_id)
    )
    cards = result.scalars().all()

    if not cards:
        return StatsResponse(
            user_id=user_id,
            total_cards=0,
            cards_by_state={},
            average_stability=0.0,
            average_interval=0.0
        )

    states = {}
    for card in cards:
        state = card.state
        states[state] = states.get(state, 0) + 1

    avg_stability = sum(c.stability for c in cards) / len(cards)
    avg_interval = sum(c.interval for c in cards) / len(cards)

    return StatsResponse(
        user_id=user_id,
        total_cards=len(cards),
        cards_by_state=states,
        average_stability=avg_stability,
        average_interval=avg_interval
    )


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(FSRSCard).filter(FSRSCard.id == card_id)
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    await db.delete(card)
    await db.commit()

    return {"message": "Card deleted successfully"}