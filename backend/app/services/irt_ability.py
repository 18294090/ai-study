from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import math
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.irt import IRTItemParams, IRTAbilityEstimate, ResponseRecord
from app.services.irt_calibration import Response


GRID_POINTS = [-3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def pdf_normal(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2.0 * math.pi))


def p_irt(theta: float, a: float, b: float, c: float = 0.0) -> float:
    exponent = -a * (theta - b)
    return c + (1 - c) / (1.0 + math.exp(exponent))


@dataclass
class AbilityResult:
    theta: float
    se: float
    based_on: int


class IRTAbilityEstimator:
    async def estimate_ability(
        self, user_id: int, subject_id: int, responses: List[Response]
    ) -> AbilityResult:
        """
        使用 Expected A Posteriori (EAP) 估计学生能力

        先验: θ ~ N(0, 1)
        后验: P(θ | responses) ∝ N(θ; 0, 1) * ∏ P(θ)

        网格点: θ ∈ {-3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3}

        返回: (theta, se, based_on)
        """
        if len(responses) < 5:
            raise ValueError("Need at least 5 responses for EAP estimation")

        weights = []
        for theta in GRID_POINTS:
            prior = pdf_normal(theta, 0.0, 1.0)
            likelihood = 1.0
            for resp in responses:
                prob = p_irt(theta, resp.ability, 0.0)
                if resp.is_correct:
                    likelihood *= prob
                else:
                    likelihood *= (1.0 - prob)
            weights.append(prior * likelihood)

        total_weight = sum(weights)
        if total_weight <= 0:
            theta_est = 0.0
            se = 1.0
        else:
            theta_est = sum(t * w for t, w in zip(GRID_POINTS, weights)) / total_weight
            variance = sum((t - theta_est) ** 2 * w for t, w in zip(GRID_POINTS, weights)) / total_weight
            se = math.sqrt(variance) if variance > 0 else 1.0

        return AbilityResult(theta=theta_est, se=se, based_on=len(responses))

    async def update_from_response(
        self,
        user_id: int,
        subject_id: int,
        question_id: int,
        correct: bool,
        response_time: float,
        db: AsyncSession,
    ) -> AbilityResult:
        """
        基于单个作答更新能力估计
        需要至少 5 次作答
        """
        stmt = select(ResponseRecord).where(
            ResponseRecord.user_id == user_id,
            ResponseRecord.question_id == question_id,
        ).order_by(ResponseRecord.recorded_at.desc())
        result = await db.execute(stmt)
        existing = result.first()
        attempt = (existing.attempt + 1) if existing else 1

        record = ResponseRecord(
            user_id=user_id,
            question_id=question_id,
            correct=correct,
            response_time=response_time,
            attempt=attempt,
            recorded_at=datetime.utcnow(),
        )
        db.add(record)

        resp_stmt = select(ResponseRecord).where(ResponseRecord.user_id == user_id)
        resp_result = await db.execute(resp_stmt)
        all_responses = resp_result.scalars().all()

        item_stmt = select(IRTItemParams).where(
            IRTItemParams.question_id == question_id,
            IRTItemParams.status == "calibrated",
        )
        item_result = await db.execute(item_stmt)
        item = item_result.scalar_one_or_none()

        responses = []
        for r in all_responses:
            item_stmt = select(IRTItemParams).where(
                IRTItemParams.question_id == r.question_id,
                IRTItemParams.status == "calibrated",
            )
            item_result = await db.execute(item_stmt)
            item_params = item_result.scalar_one_or_none()
            if item_params:
                responses.append(Response(ability=item_params.a, is_correct=r.correct))

        if len(responses) < 5:
            return AbilityResult(theta=0.0, se=1.0, based_on=len(responses))

        ability = await self.estimate_ability(user_id, subject_id, responses)

        ability_record = IRTAbilityEstimate(
            user_id=user_id,
            subject_id=subject_id,
            theta=ability.theta,
            se=ability.se,
            method="EAP",
            based_on=ability.based_on,
            estimated_at=datetime.utcnow(),
        )
        db.add(ability_record)

        await db.commit()
        return ability

    async def get_ability(
        self, user_id: int, subject_id: int, db: AsyncSession
    ) -> Optional[AbilityResult]:
        """从数据库获取最新能力估计"""
        stmt = (
            select(IRTAbilityEstimate)
            .where(
                IRTAbilityEstimate.user_id == user_id,
                IRTAbilityEstimate.subject_id == subject_id,
            )
            .order_by(IRTAbilityEstimate.estimated_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            return AbilityResult(theta=record.theta, se=record.se, based_on=record.based_on)
        return None