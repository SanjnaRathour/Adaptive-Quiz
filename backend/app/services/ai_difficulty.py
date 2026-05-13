"""Gemini-powered difficulty recommendation for the adaptive engine.

Called by the attempt service when selecting the next question in an adaptive
quiz. EMA still tracks the running ability estimate; this module decides what
difficulty the next question should be by asking Gemini to reason over the
student's recent answer history.

Falls back to the EMA-based difficulty if:
  - AI_FEEDBACK_ENABLED is false or GOOGLE_API_KEY is missing
  - The student has no answers yet (cold start — nothing to reason over)
  - Gemini returns an unexpected response
  - The API call raises any exception
"""
from __future__ import annotations

import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.models.question import Difficulty

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an adaptive quiz engine deciding what difficulty the next question "
    "should be for a student. You will receive the student's recent answer history "
    "and their current ability score (0.0 = weakest, 1.0 = strongest). "
    "Analyse the pattern — consecutive correct answers suggest moving up, "
    "consecutive wrong answers suggest moving down, mixed results suggest staying. "
    "Reply with exactly one word: EASY, MEDIUM, or HARD. "
    "No explanation, no punctuation, just the single word."
)

_SUGGEST_SYSTEM_PROMPT = (
    "You are a quiz authoring assistant. Given a quiz question, classify its "
    "difficulty as EASY, MEDIUM, or HARD using these definitions: "
    "EASY — factual recall, basic definitions, obvious single-step answers; "
    "MEDIUM — requires understanding, some reasoning, or applying a concept; "
    "HARD — deep knowledge, multi-step reasoning, analysis, or synthesis. "
    "Reply with exactly one word: EASY, MEDIUM, or HARD. "
    "No explanation, no punctuation."
)

_client: genai.Client | None = None


def _extract_response_text(resp) -> str:  # type: ignore[no-untyped-def]
    """Return the final text from a Gemini response, skipping thought parts."""
    try:
        parts = resp.candidates[0].content.parts or []
        for part in parts:
            if not getattr(part, "thought", False) and getattr(part, "text", None):
                return part.text
    except (AttributeError, IndexError, TypeError):
        pass
    return resp.text or ""


def _get_client() -> genai.Client | None:
    global _client
    if _client is not None:
        return _client
    if not settings.AI_FEEDBACK_ENABLED or not settings.GOOGLE_API_KEY:
        return None
    _client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _client


def set_client_for_testing(client: genai.Client | None) -> None:
    """Swap the Gemini client (used by tests). Pass None to revert to defaults."""
    global _client
    _client = client


def recommend_difficulty(
    recent_answers: list[dict],
    ability_estimate: float,
    fallback: Difficulty,
) -> Difficulty:
    """Ask Gemini what difficulty the next question should be.

    Args:
        recent_answers: List of dicts {"difficulty": str, "correct": bool},
                        ordered oldest-first. Built from attempt.answers.
        ability_estimate: Current EMA ability score in [0, 1].
        fallback: EMA-based difficulty to use if AI is unavailable.

    Returns the AI-recommended Difficulty, or `fallback` on any failure.
    """
    if not recent_answers:
        return fallback

    client = _get_client()
    if client is None:
        return fallback

    window = recent_answers[-6:]
    lines = "\n".join(
        f"  {i + 1}. {a['difficulty']} — {'correct' if a['correct'] else 'wrong'}"
        for i, a in enumerate(window)
    )
    prompt = (
        f"Student's recent answers (oldest first):\n{lines}\n\n"
        f"Current ability score: {ability_estimate:.2f}\n\n"
        "What difficulty should the next question be?"
    )

    try:
        resp = _get_client().models.generate_content(  # type: ignore[union-attr]
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                max_output_tokens=500,
            ),
        )
        text = _extract_response_text(resp).strip().upper().strip(".")
        if text in ("EASY", "MEDIUM", "HARD"):
            logger.debug(
                "AI difficulty → %s (ability=%.2f, last=%s)",
                text,
                ability_estimate,
                window[-1]["difficulty"],
            )
            return Difficulty(text)
        logger.warning("Unexpected AI difficulty response %r — using EMA fallback", resp.text)
    except Exception:
        logger.exception("AI difficulty call failed — using EMA fallback")

    return fallback


def suggest_question_difficulty(question_text: str) -> tuple[Difficulty, bool]:
    """Ask Gemini to suggest a difficulty label for a newly authored question.

    Returns (suggested_difficulty, ai_was_used). Falls back to MEDIUM when AI
    is unavailable so callers always get a sensible default.
    """
    client = _get_client()
    if client is None:
        return Difficulty.MEDIUM, False

    try:
        resp = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"Question: {question_text}",
            config=types.GenerateContentConfig(
                system_instruction=_SUGGEST_SYSTEM_PROMPT,
                max_output_tokens=500,
            ),
        )
        text = (_extract_response_text(resp)).strip().upper().strip(".")
        if text in ("EASY", "MEDIUM", "HARD"):
            return Difficulty(text), True
        logger.warning("Unexpected AI difficulty suggestion %r — defaulting to MEDIUM", resp.text)
    except Exception:
        logger.exception("AI difficulty suggestion failed — defaulting to MEDIUM")

    return Difficulty.MEDIUM, False
