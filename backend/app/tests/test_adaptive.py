"""Pure-logic tests for the adaptive engine — no DB or HTTP."""
from dataclasses import dataclass

from app.models.question import Difficulty
from app.services.adaptive import (
    EMA_ALPHA,
    select_next_question,
    target_difficulty,
    update_ability,
)


@dataclass
class FakeQ:
    """Minimal stand-in for app.models.question.Question (only fields the engine reads)."""

    id: str
    difficulty: Difficulty
    order_index: int = 0


def test_target_difficulty_buckets() -> None:
    assert target_difficulty(0.0) == Difficulty.EASY
    assert target_difficulty(0.39) == Difficulty.EASY
    assert target_difficulty(0.4) == Difficulty.MEDIUM
    assert target_difficulty(0.74) == Difficulty.MEDIUM
    assert target_difficulty(0.75) == Difficulty.HARD
    assert target_difficulty(1.0) == Difficulty.HARD


def test_update_ability_correct_easy_is_weak_signal() -> None:
    """Getting an EASY question right shouldn't catapult ability."""
    new = update_ability(0.5, difficulty=Difficulty.EASY, is_correct=True)
    # EASY+correct outcome is 0.45, prior 0.5 — should drift slightly DOWN.
    assert new < 0.5
    assert abs(new - (EMA_ALPHA * 0.45 + (1 - EMA_ALPHA) * 0.5)) < 1e-9


def test_update_ability_correct_hard_is_strong_signal() -> None:
    new = update_ability(0.5, difficulty=Difficulty.HARD, is_correct=True)
    # HARD+correct outcome is 0.95 — should jump up.
    assert new > 0.6


def test_update_ability_wrong_easy_is_strong_negative_signal() -> None:
    new = update_ability(0.5, difficulty=Difficulty.EASY, is_correct=False)
    assert new < 0.4


def test_update_ability_wrong_hard_is_weak_negative_signal() -> None:
    new = update_ability(0.5, difficulty=Difficulty.HARD, is_correct=False)
    assert 0.45 < new < 0.55  # barely moves


def test_update_ability_clamped() -> None:
    assert update_ability(0.0, difficulty=Difficulty.EASY, is_correct=False) >= 0.0
    assert update_ability(1.0, difficulty=Difficulty.HARD, is_correct=True) <= 1.0


def test_repeated_correct_hard_converges_high() -> None:
    a = 0.5
    for _ in range(15):
        a = update_ability(a, difficulty=Difficulty.HARD, is_correct=True)
    assert a > 0.85


def test_repeated_wrong_easy_converges_low() -> None:
    a = 0.5
    for _ in range(15):
        a = update_ability(a, difficulty=Difficulty.EASY, is_correct=False)
    assert a < 0.15


def test_select_next_question_prefers_target_tier() -> None:
    pool = [
        FakeQ("e1", Difficulty.EASY),
        FakeQ("m1", Difficulty.MEDIUM),
        FakeQ("h1", Difficulty.HARD),
    ]
    # Low ability → should pick EASY.
    assert select_next_question(pool, ability=0.1).id == "e1"
    # Mid → MEDIUM.
    assert select_next_question(pool, ability=0.5).id == "m1"
    # High → HARD.
    assert select_next_question(pool, ability=0.9).id == "h1"


def test_select_next_question_falls_back_when_target_empty() -> None:
    # Ability says HARD, but no HARD available — should fall back to MEDIUM.
    pool = [FakeQ("m1", Difficulty.MEDIUM), FakeQ("e1", Difficulty.EASY)]
    chosen = select_next_question(pool, ability=0.95)
    assert chosen.id == "m1"


def test_select_next_question_returns_none_for_empty_pool() -> None:
    assert select_next_question([], ability=0.5) is None
