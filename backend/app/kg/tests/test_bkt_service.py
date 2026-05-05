import pytest
import sys
sys.path.insert(0, '/home/zh/ai-study/backend')

from app.services.bkt_service import BKTUpdater, MasteryState


def test_bkt_update_correct_increases_mastery():
    updater = BKTUpdater(p_guess=0.1, p_slip=0.2)
    p = 0.5
    p_new = updater.update(p, is_correct=True)
    assert p_new > p  # correct answer should increase mastery


def test_bkt_update_incorrect_decreases_mastery():
    updater = BKTUpdater(p_guess=0.1, p_slip=0.2)
    p = 0.5
    p_new = updater.update(p, is_correct=False)
    assert p_new < p  # incorrect answer should decrease mastery


def test_bkt_stays_in_bounds():
    updater = BKTUpdater()
    p = 0.5
    for _ in range(100):
        p = updater.update(p, is_correct=True)
        p = updater.update(p, is_correct=False)
    assert 0.0 <= p <= 1.0


def test_bkt_apply_forget():
    updater = BKTUpdater(p_forget=0.05)
    p = 0.8
    p_decayed = updater.apply_forget(p, time_elapsed_hours=1.0)
    assert p_decayed < p  # forgetting should decrease mastery


def test_mastery_state_to_dict():
    state = MasteryState(p_know=0.75, attempts=5, correct_count=3)
    d = state.to_dict()
    assert d["p_know"] == 0.75
    assert d["attempts"] == 5
    assert d["correct_count"] == 3


def test_mastery_state_from_dict():
    d = {"p_know": 0.6, "attempts": 10, "correct_count": 7}
    state = MasteryState.from_dict(d)
    assert state.p_know == 0.6
    assert state.attempts == 10
    assert state.correct_count == 7


def test_compute_initial_p():
    updater = BKTUpdater()
    p = updater.compute_initial_p(3, 5)  # 3 correct out of 5
    assert 0.1 < p < 0.9


def test_compute_initial_p_zero_attempts():
    updater = BKTUpdater()
    p = updater.compute_initial_p(0, 0)
    assert p == 0.3  # default