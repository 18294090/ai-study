from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()


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


class FSRSState:
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    RELARNING = "relearning"


class FSRSMemory:
    def __init__(self, stability: float = 0.0, difficulty: float = 0.0):
        self.stability = stability
        self.difficulty = difficulty

    def record_review(self, rating: int, response_time: float) -> tuple[float, float, float]:
        if rating >= 3:
            new_stability = self.stability * (1 + 0.1 * (rating - 3) - 0.05 * response_time / 1000)
            new_stability = max(0.1, new_stability)
        else:
            new_stability = self.stability * (0.5 - 0.1 * rating)
            new_stability = max(0.1, new_stability)

        if rating >= 3:
            new_difficulty = self.difficulty + 0.1 * (rating - 3) - 0.02
        else:
            new_difficulty = self.difficulty + 0.1 * (rating - 2)

        new_difficulty = max(0.1, min(5.0, new_difficulty))

        interval = new_stability * 1.5 if rating >= 3 else 0.1
        retrievability = 1.0 - 0.5 ** (1.0 / new_stability)

        self.stability = new_stability
        self.difficulty = new_difficulty

        return interval, new_stability, retrievability


_in_memory_cards: dict[int, dict] = {}
_card_id_counter = 1


@router.post("/cards", response_model=CardResponse, status_code=201)
async def create_card(
    request: CreateCardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    global _card_id_counter

    stability = request.initial_stability if request.initial_stability is not None else 0.5
    difficulty = request.initial_difficulty if request.initial_difficulty is not None else 2.5

    card = {
        "card_id": _card_id_counter,
        "user_id": request.user_id,
        "concept_id": request.concept_id,
        "state": FSRSState.NEW,
        "stability": stability,
        "difficulty": difficulty,
        "interval": 0.0,
        "due": datetime.now(timezone.utc),
    }
    _in_memory_cards[_card_id_counter] = card
    _card_id_counter += 1

    return CardResponse(
        card_id=card["card_id"],
        user_id=card["user_id"],
        concept_id=card["concept_id"],
        state=card["state"],
        stability=card["stability"],
        interval=card["interval"],
        due=card["due"],
    )


@router.post("/review", response_model=ReviewResponse)
async def review_card(
    request: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if request.rating < 1 or request.rating > 4:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 4")

    card = _in_memory_cards.get(request.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    memory = FSRSMemory(stability=card["stability"], difficulty=card["difficulty"])
    interval, new_stability, retrievability = memory.record_review(request.rating, request.response_time)

    next_due = datetime.now(timezone.utc).replace(microsecond=0)
    if interval >= 1:
        from datetime import timedelta
        next_due = datetime.now(timezone.utc) + timedelta(days=interval)
    else:
        from datetime import timedelta
        next_due = datetime.now(timezone.utc) + timedelta(minutes=interval * 1440)

    card["stability"] = new_stability
    card["interval"] = interval
    card["due"] = next_due
    card["state"] = FSRSState.REVIEW if request.rating >= 3 else FSRSState.LEARNING

    return ReviewResponse(
        card_id=card["card_id"],
        next_interval=interval,
        next_due=next_due,
        stability=new_stability,
        retrievability=retrievability,
    )


@router.get("/due/{user_id}", response_model=DueResponse)
async def get_due_cards(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    due_cards = []

    for card in _in_memory_cards.values():
        if card["user_id"] == user_id and card["due"] <= now:
            due_cards.append(DueCardResponse(
                card_id=card["card_id"],
                concept_id=card["concept_id"],
                state=card["state"],
                due=card["due"],
                interval=card["interval"],
                stability=card["stability"],
            ))

    return DueResponse(cards=due_cards, total_due=len(due_cards))


@router.get("/stats/{user_id}", response_model=StatsResponse)
async def get_stats(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_cards = [c for c in _in_memory_cards.values() if c["user_id"] == user_id]

    if not user_cards:
        return StatsResponse(
            user_id=user_id,
            total_cards=0,
            cards_by_state={},
            average_stability=0.0,
            average_interval=0.0,
        )

    states = {}
    for card in user_cards:
        state = card["state"]
        states[state] = states.get(state, 0) + 1

    avg_stability = sum(c["stability"] for c in user_cards) / len(user_cards)
    avg_interval = sum(c["interval"] for c in user_cards) / len(user_cards)

    return StatsResponse(
        user_id=user_id,
        total_cards=len(user_cards),
        cards_by_state=states,
        average_stability=avg_stability,
        average_interval=avg_interval,
    )


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if card_id not in _in_memory_cards:
        raise HTTPException(status_code=404, detail="Card not found")

    del _in_memory_cards[card_id]
    return {"message": "Card deleted successfully"}