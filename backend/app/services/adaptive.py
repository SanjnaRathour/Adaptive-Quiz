"""Adaptive difficulty engine.

Rule-based: maintains a per-attempt ability estimate in [0, 1] using an
exponential moving average over difficulty-weighted outcomes, then picks the
next question whose difficulty matches the student's current ability band.

Kept fully pure (no DB writes) so it's trivially unit-testable; the attempt
service is responsible for persisting any updates.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models.question import Difficulty, Question

# Smoothing factor for the EMA — higher values make the estimate adapt faster
# but less stably. 0.4 lets ~3 answers shift the band while still treating the
# prior as meaningful.
EMA_ALPHA = 0.4

# How strong a signal each outcome is, as a value in [0, 1] for the EMA target.
# Getting an EASY question right is weak evidence of high ability; getting a
# HARD question wrong is weak evidence of low ability — and vice versa.
_OUTCOME_TABLE: dict[tuple[Difficulty, bool], float] = {
    (Difficulty.EASY, True): 0.45,
    (Difficulty.MEDIUM, True): 0.65,
    (Difficulty.HARD, True): 0.95,
    (Difficulty.EASY, False): 0.05,
    (Difficulty.MEDIUM, False): 0.35,
    (Difficulty.HARD, False): 0.55,
}


def update_ability(prior: float, *, difficulty: Difficulty, is_correct: bool) -> float:
    """EMA update: new = alpha * outcome + (1-alpha) * prior, clamped to [0, 1]."""
    target = _OUTCOME_TABLE[(difficulty, is_correct)]
    new = EMA_ALPHA * target + (1 - EMA_ALPHA) * prior
    return max(0.0, min(1.0, new))


def target_difficulty(ability: float) -> Difficulty:
    """Bucket ability into a difficulty tier for the next question."""
    if ability < 0.4:
        return Difficulty.EASY
    if ability < 0.75:
        return Difficulty.MEDIUM
    return Difficulty.HARD


@dataclass(frozen=True)
class _Bucketed:
    easy: list[Question]
    medium: list[Question]
    hard: list[Question]

    def at(self, d: Difficulty) -> list[Question]:
        return {Difficulty.EASY: self.easy, Difficulty.MEDIUM: self.medium, Difficulty.HARD: self.hard}[d]


def _bucket(questions: Iterable[Question]) -> _Bucketed:
    e: list[Question] = []
    m: list[Question] = []
    h: list[Question] = []
    for q in questions:
        if q.difficulty == Difficulty.EASY:
            e.append(q)
        elif q.difficulty == Difficulty.MEDIUM:
            m.append(q)
        else:
            h.append(q)
    return _Bucketed(e, m, h)


# Fallback order for each target — try the target tier first, then adjacent
# ones, so we always return *something* when any unanswered question exists.
_FALLBACK_ORDER: dict[Difficulty, tuple[Difficulty, ...]] = {
    Difficulty.EASY: (Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD),
    Difficulty.MEDIUM: (Difficulty.MEDIUM, Difficulty.EASY, Difficulty.HARD),
    Difficulty.HARD: (Difficulty.HARD, Difficulty.MEDIUM, Difficulty.EASY),
}


def select_next_question(
    candidates: Iterable[Question],
    *,
    ability: float,
) -> Question | None:
    """Pick the next question for a given ability from the unanswered pool.

    Strategy: bucket candidates by difficulty, pick the first available in the
    target tier; if empty, fall back to the next-closest tier. Within a tier we
    take the first by `order_index, created_at` (the caller is expected to pass
    the candidates already sorted that way).
    """
    target = target_difficulty(ability)
    buckets = _bucket(candidates)
    for tier in _FALLBACK_ORDER[target]:
        bucket = buckets.at(tier)
        if bucket:
            return bucket[0]
    return None
