from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from app.models.base import Base


@dataclass
class FSRSCard:
    """FSRS 卡片状态"""
    id: int
    user_id: int
    concept_id: int
    stability: float
    difficulty: float
    state: str
    lapses: int
    reps: int
    due: datetime
    last_review: Optional[datetime] = None


@dataclass
class ScheduleResult:
    """调度结果"""
    next_interval: float
    next_stability: float
    next_difficulty: float
    due: datetime
    state: str


@dataclass
class FSRSReviewLog:
    """FSRS 复习记录"""
    id: int
    card_id: int
    rating: int
    response_time: float
    stability_before: float
    difficulty_before: float
    stability_after: float
    difficulty_after: float
    interval_before: float
    interval_after: float
    reviewed_at: datetime


class FSRSOptimizer:
    """FSRS 参数优化器"""
    DEFAULT_W = [
        0.4, 0.6, 2.4, 2.9, 4.9,
        0.2, 1.3, 0.1, 0.1, 0.1
    ]

    def stability_after(self, s: float, r: float, w: List[float]) -> float:
        """计算 rating 后的新稳定度"""
        return s * (1 + (2.5 ** (r - 1)) - 2.5 * (2.5 ** (r - 1) - 1) / (1 + 9.2 / w[3] ** 4))

    def difficulty_after(self, d: float, r: int, w: List[float]) -> float:
        """计算 rating 后的新难度"""
        if r >= 3:
            return max(1.3, min(4.5, d - 0.14 + 0.14 * (r - 2)))
        else:
            return max(1.3, min(4.5, d + 0.14))

    def interval_after(self, stability: float, difficulty: float, r: int, w: List[float]) -> float:
        """计算 rating 后的新间隔（天）"""
        if r == 1:
            return 1.0 / 1440
        elif r == 2:
            return max(1.0 / 1440, stability * w[3] / (difficulty - 1.3))
        elif r == 3:
            return stability / (difficulty - 1)
        else:
            return stability * w[4] / (difficulty - 1)


class FSRSScheduler:
    """FSRS 调度器"""

    def __init__(self, w: Optional[List[float]] = None):
        self.optimizer = FSRSOptimizer()
        self.w = w or FSRSOptimizer.DEFAULT_W

    def schedule(self, card: FSRSCard, rating: int) -> ScheduleResult:
        """
        rating: 1=again, 2=hard, 3=good, 4=easy
        """
        stability = card.stability
        difficulty = card.difficulty
        interval = 0.0

        if card.last_review and card.state != "new":
            elapsed = (datetime.utcnow() - card.last_review).total_seconds() / 86400
            stability = stability * 0.9 ** elapsed

        if rating == 1:
            new_state = "relearning"
            new_stability = stability * self.w[7]
            new_difficulty = self.optimizer.difficulty_after(difficulty, rating, self.w)
            interval = 1.0 / 1440
            card.lapses += 1
        elif rating == 2:
            new_state = card.state
            new_stability = stability * self.w[8]
            new_difficulty = self.optimizer.difficulty_after(difficulty, rating, self.w)
            interval = card.stability * self.w[3] if card.stability > 0 else 1.0
        elif rating == 3:
            new_state = card.state
            new_stability = stability * self.w[3]
            new_difficulty = self.optimizer.difficulty_after(difficulty, rating, self.w)
            interval = stability / (difficulty - 1) if difficulty > 1 else stability
        else:
            new_state = card.state
            new_stability = stability * self.w[9]
            new_difficulty = self.optimizer.difficulty_after(difficulty, rating, self.w)
            interval = stability * self.w[4] * self.w[3] / (difficulty - 1) if difficulty > 1 else stability * self.w[4]

        interval = max(1.0 / 1440, interval)
        due = datetime.utcnow() + timedelta(days=interval)

        return ScheduleResult(
            next_interval=interval,
            next_stability=new_stability,
            next_difficulty=new_difficulty,
            due=due,
            state=new_state
        )

    async def get_due_cards(
        self,
        user_id: int,
        limit: int,
        concept_ids: List[int],
        db: AsyncSession
    ) -> List[FSRSCard]:
        """获取待复习卡片"""
        from app.models.base import Base
        from sqlalchemy import select

        metadata = Base.metadata
        if "fsrs_cards" not in metadata.tables:
            return []

        now = datetime.utcnow()
        stmt = (
            select(metadata.tables["fsrs_cards"])
            .where(
                metadata.tables["fsrs_cards"].c.user_id == user_id,
                metadata.tables["fsrs_cards"].c.concept_id.in_(concept_ids),
                metadata.tables["fsrs_cards"].c.due <= now
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.fetchall()

        cards = []
        for row in rows:
            cards.append(FSRSCard(
                id=row.id,
                user_id=row.user_id,
                concept_id=row.concept_id,
                stability=row.stability,
                difficulty=row.difficulty,
                state=row.state,
                lapses=row.lapses,
                reps=row.reps,
                due=row.due,
                last_review=row.last_review
            ))
        return cards

    async def create_card(
        self,
        user_id: int,
        concept_id: int,
        initial_stability: float,
        initial_difficulty: float,
        db: AsyncSession
    ) -> FSRSCard:
        """创建新卡片"""
        from app.models.base import Base

        metadata = Base.metadata
        table_name = "fsrs_cards"
        if table_name not in metadata.tables:
            from sqlalchemy import Table, Column, Integer, Float, String, DateTime
            from sqlalchemy.sql import func

            new_table = Table(
                table_name,
                metadata,
                Column("id", Integer, primary_key=True, index=True),
                Column("user_id", Integer, nullable=False, index=True),
                Column("concept_id", String, nullable=False, index=True),
                Column("stability", Float, nullable=False, default=0.0),
                Column("difficulty", Float, nullable=False, default=2.5),
                Column("state", String, nullable=False, default="new"),
                Column("lapses", Integer, default=0),
                Column("reps", Integer, default=0),
                Column("due", DateTime, nullable=False, default=func.now()),
                Column("last_review", DateTime, nullable=True),
                extend_existing=True
            )
            metadata.create_all(db.bind, tables=[new_table])

        now = datetime.utcnow()
        new_card = FSRSCard(
            id=0,
            user_id=user_id,
            concept_id=concept_id,
            stability=initial_stability,
            difficulty=initial_difficulty,
            state="new",
            lapses=0,
            reps=0,
            due=now,
            last_review=None
        )

        stmt = (
            metadata.tables[table_name].insert()
            .values(
                user_id=user_id,
                concept_id=concept_id,
                stability=initial_stability,
                difficulty=initial_difficulty,
                state="new",
                lapses=0,
                reps=0,
                due=now,
                last_review=None
            )
            .returning(metadata.tables[table_name].c.id)
        )
        result = await db.execute(stmt)
        row = result.fetchone()
        new_card.id = row.id
        return new_card

    async def record_review(
        self,
        card_id: int,
        rating: int,
        response_time: float,
        db: AsyncSession
    ) -> FSRSReviewLog:
        """记录复习并更新卡片状态"""
        from app.models.base import Base

        metadata = Base.metadata
        cards_table = metadata.tables.get("fsrs_cards")
        logs_table = metadata.tables.get("fsrs_review_logs")

        if cards_table is None:
            raise ValueError("fsrs_cards table not initialized")

        stmt = select(cards_table).where(cards_table.c.id == card_id)
        result = await db.execute(stmt)
        row = result.fetchone()
        if not row:
            raise ValueError(f"Card {card_id} not found")

        card = FSRSCard(
            id=row.id,
            user_id=row.user_id,
            concept_id=row.concept_id,
            stability=row.stability,
            difficulty=row.difficulty,
            state=row.state,
            lapses=row.lapses,
            reps=row.reps,
            due=row.due,
            last_review=row.last_review
        )

        schedule_result = self.schedule(card, rating)
        now = datetime.utcnow()

        stability_before = card.stability
        difficulty_before = card.difficulty
        interval_before = 0.0
        if card.last_review:
            interval_before = (card.last_review - (card.due - timedelta(days=card.stability))).total_seconds() / 86400 if card.stability > 0 else 0.0

        card.stability = schedule_result.next_stability
        card.difficulty = schedule_result.next_difficulty
        card.state = schedule_result.state
        card.due = schedule_result.due
        card.last_review = now
        card.reps += 1

        update_stmt = (
            cards_table.update()
            .where(cards_table.c.id == card_id)
            .values(
                stability=card.stability,
                difficulty=card.difficulty,
                state=card.state,
                due=card.due,
                last_review=card.last_review,
                lapses=card.lapses,
                reps=card.reps
            )
        )
        await db.execute(update_stmt)

        if logs_table is None:
            from sqlalchemy import Table, Column, Integer, Float, DateTime
            logs_table = Table(
                "fsrs_review_logs",
                metadata,
                Column("id", Integer, primary_key=True, index=True),
                Column("card_id", Integer, ForeignKey("fsrs_cards.id"), index=True),
                Column("rating", Integer, nullable=False),
                Column("response_time", Float, nullable=False),
                Column("stability_before", Float, nullable=False),
                Column("difficulty_before", Float, nullable=False),
                Column("stability_after", Float, nullable=False),
                Column("difficulty_after", Float, nullable=False),
                Column("interval_before", Float, nullable=False),
                Column("interval_after", Float, nullable=False),
                Column("reviewed_at", DateTime, nullable=False, default=now),
                extend_existing=True
            )
            metadata.create_all(db.bind, tables=[logs_table])

        log_stmt = (
            logs_table.insert()
            .values(
                card_id=card_id,
                rating=rating,
                response_time=response_time,
                stability_before=stability_before,
                difficulty_before=difficulty_before,
                stability_after=card.stability,
                difficulty_after=card.difficulty,
                interval_before=interval_before,
                interval_after=schedule_result.next_interval,
                reviewed_at=now
            )
            .returning(logs_table.c.id)
        )
        log_result = await db.execute(log_stmt)
        log_row = log_result.fetchone()

        return FSRSReviewLog(
            id=log_row.id,
            card_id=card_id,
            rating=rating,
            response_time=response_time,
            stability_before=stability_before,
            difficulty_before=difficulty_before,
            stability_after=card.stability,
            difficulty_after=card.difficulty,
            interval_before=interval_before,
            interval_after=schedule_result.next_interval,
            reviewed_at=now
        )
