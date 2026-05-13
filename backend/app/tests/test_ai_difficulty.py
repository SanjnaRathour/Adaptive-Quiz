"""Tests for the AI difficulty recommendation service — Gemini client is mocked.

All tests are pure-logic (no DB, no HTTP). The fake Gemini client is injected
via ai_difficulty.set_client_for_testing() and reset after every test by the
autouse fixture.
"""
from __future__ import annotations

from typing import Any

import pytest

from app.models.question import Difficulty
from app.services import ai_difficulty
from app.services.ai_difficulty import recommend_difficulty

# ---------------------------------------------------------------------------
# Fake Gemini client
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, text: str | None) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, response_text: str | None = "MEDIUM") -> None:
        self.response_text = response_text
        self.calls: list[str] = []

    def generate_content(self, *, model: str, contents: str, config: Any) -> _FakeResp:
        self.calls.append(contents)
        return _FakeResp(self.response_text)


class _FakeClient:
    def __init__(self, response_text: str | None = "MEDIUM") -> None:
        self.models = _FakeModels(response_text)

    @property
    def calls(self) -> list[str]:
        return self.models.calls


class _ErrorModels:
    """Gemini models stub that always raises."""

    def generate_content(self, **_: Any) -> None:
        raise RuntimeError("network timeout")


class _ErrorClient:
    models = _ErrorModels()


@pytest.fixture(autouse=True)
def _reset_ai_client() -> Any:
    """Reset the module-level client after every test."""
    yield
    ai_difficulty.set_client_for_testing(None)


# ---------------------------------------------------------------------------
# Fallback cases — Gemini must NOT be called
# ---------------------------------------------------------------------------

def test_returns_fallback_when_no_answers() -> None:
    """Cold start: no answer history yet → skip AI, use EMA fallback."""
    fake = _FakeClient("HARD")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty([], 0.5, Difficulty.MEDIUM)

    assert result == Difficulty.MEDIUM
    assert fake.calls == []  # AI was never called


def test_returns_fallback_when_client_is_none() -> None:
    """AI disabled / no API key → return EMA fallback immediately."""
    ai_difficulty.set_client_for_testing(None)

    result = recommend_difficulty(
        [{"difficulty": "EASY", "correct": True}], 0.5, Difficulty.EASY
    )

    assert result == Difficulty.EASY


def test_returns_fallback_on_unrecognised_response() -> None:
    """Gemini replies with something other than EASY / MEDIUM / HARD."""
    fake = _FakeClient("I'd suggest medium, actually")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "MEDIUM", "correct": False}], 0.4, Difficulty.EASY
    )

    assert result == Difficulty.EASY  # fallback


def test_returns_fallback_on_empty_response() -> None:
    """Gemini returns an empty string."""
    fake = _FakeClient("")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "HARD", "correct": True}], 0.8, Difficulty.HARD
    )

    assert result == Difficulty.HARD


def test_returns_fallback_on_none_response() -> None:
    """Gemini returns None (no candidates)."""
    fake = _FakeClient(None)
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "HARD", "correct": True}], 0.8, Difficulty.HARD
    )

    assert result == Difficulty.HARD


def test_returns_fallback_when_ai_raises() -> None:
    """Any exception from Gemini is swallowed and fallback is returned."""
    ai_difficulty.set_client_for_testing(_ErrorClient())  # type: ignore[arg-type]

    result = recommend_difficulty(
        [{"difficulty": "MEDIUM", "correct": True}], 0.6, Difficulty.MEDIUM
    )

    assert result == Difficulty.MEDIUM  # never propagates the exception


# ---------------------------------------------------------------------------
# Happy-path: AI returns valid difficulty
# ---------------------------------------------------------------------------

def test_returns_easy_when_ai_says_easy() -> None:
    fake = _FakeClient("EASY")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "MEDIUM", "correct": False}], 0.35, Difficulty.MEDIUM
    )

    assert result == Difficulty.EASY


def test_returns_medium_when_ai_says_medium() -> None:
    fake = _FakeClient("MEDIUM")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "EASY", "correct": True}], 0.5, Difficulty.EASY
    )

    assert result == Difficulty.MEDIUM


def test_returns_hard_when_ai_says_hard() -> None:
    fake = _FakeClient("HARD")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "HARD", "correct": True}], 0.8, Difficulty.HARD
    )

    assert result == Difficulty.HARD


def test_response_with_trailing_period_is_accepted() -> None:
    """Gemini occasionally appends punctuation — strip it and parse."""
    fake = _FakeClient("HARD.")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "HARD", "correct": True}], 0.9, Difficulty.MEDIUM
    )

    assert result == Difficulty.HARD


def test_lowercase_response_is_accepted() -> None:
    """Case-insensitive — 'easy' should resolve to Difficulty.EASY."""
    fake = _FakeClient("easy")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "MEDIUM", "correct": False}], 0.3, Difficulty.MEDIUM
    )

    assert result == Difficulty.EASY


def test_mixed_case_response_is_accepted() -> None:
    """'Medium' (title-case) should resolve correctly."""
    fake = _FakeClient("Medium")
    ai_difficulty.set_client_for_testing(fake)

    result = recommend_difficulty(
        [{"difficulty": "EASY", "correct": True}], 0.5, Difficulty.EASY
    )

    assert result == Difficulty.MEDIUM


# ---------------------------------------------------------------------------
# Prompt content checks — verifies what the AI actually receives
# ---------------------------------------------------------------------------

def test_prompt_contains_difficulty_labels() -> None:
    """Prompt must show the difficulty of each recent answer."""
    fake = _FakeClient("MEDIUM")
    ai_difficulty.set_client_for_testing(fake)

    recommend_difficulty(
        [
            {"difficulty": "EASY", "correct": True},
            {"difficulty": "MEDIUM", "correct": False},
        ],
        0.45,
        Difficulty.MEDIUM,
    )

    prompt = fake.calls[0]
    assert "EASY" in prompt
    assert "MEDIUM" in prompt


def test_prompt_contains_correct_and_wrong_labels() -> None:
    """Prompt must distinguish correct from wrong answers."""
    fake = _FakeClient("EASY")
    ai_difficulty.set_client_for_testing(fake)

    recommend_difficulty(
        [
            {"difficulty": "EASY", "correct": True},
            {"difficulty": "MEDIUM", "correct": False},
        ],
        0.4,
        Difficulty.EASY,
    )

    prompt = fake.calls[0]
    assert "correct" in prompt
    assert "wrong" in prompt


def test_prompt_includes_ability_score() -> None:
    """Ability score must appear in the prompt so Gemini can reason about it."""
    fake = _FakeClient("HARD")
    ai_difficulty.set_client_for_testing(fake)

    recommend_difficulty(
        [{"difficulty": "HARD", "correct": True}], 0.82, Difficulty.HARD
    )

    assert "0.82" in fake.calls[0]


def test_prompt_windows_to_last_6_answers() -> None:
    """Only the last 6 answers are sent — older ones are dropped."""
    fake = _FakeClient("MEDIUM")
    ai_difficulty.set_client_for_testing(fake)

    # 10 answers total; window should be the last 6
    answers = [{"difficulty": "EASY", "correct": True}] * 4 + \
              [{"difficulty": "HARD", "correct": False}] * 6

    recommend_difficulty(answers, 0.5, Difficulty.MEDIUM)

    prompt = fake.calls[0]
    # Numbered list goes 1–6, never 7+
    assert "6." in prompt
    assert "7." not in prompt


def test_ai_called_exactly_once_per_recommendation() -> None:
    """One recommend_difficulty call → exactly one Gemini API call."""
    fake = _FakeClient("EASY")
    ai_difficulty.set_client_for_testing(fake)

    recommend_difficulty(
        [{"difficulty": "EASY", "correct": False}] * 3, 0.2, Difficulty.EASY
    )

    assert len(fake.calls) == 1


def test_all_correct_history_prompts_for_harder_question() -> None:
    """Successive correct answers → AI should suggest HARD (integration check)."""
    fake = _FakeClient("HARD")
    ai_difficulty.set_client_for_testing(fake)

    answers = [{"difficulty": "MEDIUM", "correct": True}] * 4
    result = recommend_difficulty(answers, 0.72, Difficulty.MEDIUM)

    assert result == Difficulty.HARD
    # Verify the prompt actually reflects all correct
    assert fake.calls[0].count("correct") >= 4


def test_all_wrong_history_prompts_for_easier_question() -> None:
    """Successive wrong answers → AI should suggest EASY (integration check)."""
    fake = _FakeClient("EASY")
    ai_difficulty.set_client_for_testing(fake)

    answers = [{"difficulty": "MEDIUM", "correct": False}] * 4
    result = recommend_difficulty(answers, 0.3, Difficulty.MEDIUM)

    assert result == Difficulty.EASY
    assert fake.calls[0].count("wrong") >= 4
