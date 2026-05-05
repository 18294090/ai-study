from dataclasses import dataclass
from typing import List, Optional
import math


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def phi_inv(p: float) -> float:
    if p <= 0:
        return -3.0
    if p >= 1:
        return 3.0
    return _approx_phi_inv(p)


def _approx_phi_inv(p: float) -> float:
    sign = -1 if p < 0.5 else 1
    p_adj = p if p <= 0.5 else 1 - p
    if p_adj < 0.0001:
        return sign * 3.5
    t = math.sqrt(-2.0 * math.log(p_adj))
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308
    z = t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t)
    return sign * z


@dataclass
class Response:
    ability: float
    is_correct: bool


@dataclass
class IRTItemParamsResult:
    question_id: int
    a: float
    b: float
    se_a: float
    se_b: float
    info: str
    converged: bool
    iterations: int


@dataclass
class Question:
    id: int
    content: str = ""
    options: List[str] = None

    def __post_init__(self):
        if self.options is None:
            self.options = []


class IRTCalibrationService:

    def __init__(self, max_iterations: int = 50, tolerance: float = 0.001):
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.a_min, self.a_max = 0.3, 2.5
        self.b_min, self.b_max = -3.0, 3.0

    def calibrate_item(self, question_id: int, responses: List[Response]) -> IRTItemParamsResult:
        if len(responses) < 30:
            return IRTItemParamsResult(
                question_id=question_id,
                a=1.0, b=0.0,
                se_a=0.0, se_b=0.0,
                info="Insufficient responses (need >= 30)",
                converged=False,
                iterations=0
            )

        abilities = [r.ability for r in responses]
        corrects = [1 if r.is_correct else 0 for r in responses]

        accuracy = sum(corrects) / len(corrects)
        b_init = phi_inv(accuracy) if accuracy > 0 and accuracy < 1 else 0.0
        a_init = 1.0

        a, b = a_init, b_init

        for iteration in range(1, self.max_iterations + 1):
            grad_a, grad_b = 0.0, 0.0
            hess_aa, hess_bb = 0.0, 0.0

            for theta, correct in zip(abilities, corrects):
                p = logistic(a * (theta - b))
                p = max(1e-10, min(1 - 1e-10, p))
                q = 1.0 - p

                residual = correct - p
                grad_b += residual * a
                grad_a += residual * (theta - b)

                hess_bb -= a * a * p * q
                hess_aa -= p * q * (theta - b) * (theta - b)

            grad_b = grad_b
            grad_a = grad_a

            if hess_bb == 0 or hess_aa == 0:
                break

            delta_b = -grad_b / hess_bb
            delta_a = -grad_a / hess_aa

            b = b + delta_b
            a = a + delta_a

            if b < self.b_min:
                b = self.b_min
            elif b > self.b_max:
                b = self.b_max

            if a < self.a_min:
                a = self.a_min
            elif a > self.a_max:
                a = self.a_max

            if abs(delta_a) < self.tolerance and abs(delta_b) < self.tolerance:
                return IRTItemParamsResult(
                    question_id=question_id,
                    a=round(a, 4),
                    b=round(b, 4),
                    se_a=round(self._compute_se_a(a, b, abilities, corrects), 4),
                    se_b=round(self._compute_se_b(a, b, abilities, corrects), 4),
                    info="Converged successfully",
                    converged=True,
                    iterations=iteration
                )

        return IRTItemParamsResult(
            question_id=question_id,
            a=round(a, 4),
            b=round(b, 4),
            se_a=round(self._compute_se_a(a, b, abilities, corrects), 4),
            se_b=round(self._compute_se_b(a, b, abilities, corrects), 4),
            info="Max iterations reached",
            converged=False,
            iterations=self.max_iterations
        )

    def _compute_se_a(self, a: float, b: float, abilities: List[float], corrects: List[int]) -> float:
        info = 0.0
        for theta, correct in zip(abilities, corrects):
            p = logistic(a * (theta - b))
            p = max(1e-10, min(1 - 1e-10, p))
            q = 1.0 - p
            info += p * q * (theta - b) * (theta - b)
        if info <= 0:
            return 0.0
        return 1.0 / math.sqrt(info)

    def _compute_se_b(self, a: float, b: float, abilities: List[float], corrects: List[int]) -> float:
        info = 0.0
        for theta, correct in zip(abilities, corrects):
            p = logistic(a * (theta - b))
            p = max(1e-10, min(1 - 1e-10, p))
            q = 1.0 - p
            info += a * a * p * q
        if info <= 0:
            return 0.0
        return 1.0 / math.sqrt(info)

    async def calibrate_batch(self, question_ids: List[int], db) -> List[IRTItemParamsResult]:
        from sqlalchemy import text
        results = []

        for question_id in question_ids:
            result = await db.execute(
                text("""
                    SELECT ability, is_correct
                    FROM responses
                    WHERE question_id = :qid AND ability IS NOT NULL
                    LIMIT 200
                """),
                {"qid": question_id}
            )
            rows = result.fetchall()

            responses = [
                Response(ability=row.ability, is_correct=bool(row.is_correct))
                for row in rows
            ]

            calibrated = self.calibrate_item(question_id, responses)
            results.append(calibrated)

        return results

    async def estimate_from_llm(self, question: Question, llm_client) -> float:
        prompt = (
            f"Estimate the difficulty of this multiple-choice question on a standard IRT scale.\n"
            f"Return only a single float value between -3 (very easy) and +3 (very hard).\n"
            f"Use 0 as the average difficulty.\n\n"
            f"Question: {question.content}\n"
        )
        if question.options:
            prompt += f"Options: {'; '.join(question.options)}\n"

        try:
            response = llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=20
            )
            text = response.choices[0].message.content.strip()
            b_value = float(text)
            return max(self.b_min, min(self.b_max, b_value))
        except Exception:
            return 0.0