from dataclasses import dataclass
from typing import Optional


@dataclass
class BKTParams:
    p_guess: float = 0.1   # P(L) - lucky guess probability
    p_slip: float = 0.2    # P(S) - slip probability
    p_forget: float = 0.05  # P(T) - forget probability per hour

    def validate(self):
        assert 0 <= self.p_guess <= 1
        assert 0 <= self.p_slip <= 1
        assert 0 <= self.p_forget <= 1


class BKTUpdater:
    def __init__(self, p_guess: float = 0.1, p_slip: float = 0.2, p_forget: float = 0.05):
        self.params = BKTParams(p_guess=p_guess, p_slip=p_slip, p_forget=p_forget)

    def update(self, p_know: float, is_correct: bool) -> float:
        """Update mastery probability based on answer correctness"""
        p_guess = self.params.p_guess
        p_slip = self.params.p_slip

        if is_correct:
            numerator = p_know * (1 - p_slip)
            denominator = p_know * (1 - p_slip) + (1 - p_know) * p_guess
        else:
            numerator = p_know * p_slip
            denominator = p_know * p_slip + (1 - p_know) * (1 - p_guess)

        if denominator > 0:
            p_know = numerator / denominator
        else:
            p_know = 0.0

        return max(0.0, min(1.0, p_know))

    def apply_forget(self, p_know: float, time_elapsed_hours: float) -> float:
        """Apply forgetting decay based on time elapsed"""
        decay_factor = (1 - self.params.p_forget) ** time_elapsed_hours
        return p_know * decay_factor

    def compute_initial_p(self, correct_count: int, total_attempts: int) -> float:
        """Compute initial mastery probability from diagnostic test results"""
        if total_attempts == 0:
            return 0.3  # default initial mastery
        raw_ratio = correct_count / total_attempts
        # BKT-smoothed initial probability with regularization toward 0.5
        n = total_attempts
        smoothed = (raw_ratio * n + 0.5 * 3) / (n + 3)
        return max(0.1, min(0.9, smoothed))


class MasteryState:
    def __init__(self, p_know: float, attempts: int, correct_count: int):
        self.p_know = p_know
        self.attempts = attempts
        self.correct_count = correct_count

    def to_dict(self) -> dict:
        return {
            "p_know": self.p_know,
            "attempts": self.attempts,
            "correct_count": self.correct_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MasteryState":
        return cls(
            p_know=data.get("p_know", 0.3),
            attempts=data.get("attempts", 0),
            correct_count=data.get("correct_count", 0),
        )