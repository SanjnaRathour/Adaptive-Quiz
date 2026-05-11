"""Gemini-powered personalized feedback for wrong answers.

Runs in a FastAPI BackgroundTask so submit_answer stays fast. If the API key
isn't configured or the call fails, the answer is left without ai_feedback
(the result endpoint just won't show one) — never breaks the user flow.
"""
from __future__ import annotations

import logging
import uuid
from typing import Protocol

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.database import SessionLocal as _DefaultSessionLocal
from app.models.attempt import Answer
from app.models.question import Question
from app.services.grading import correct_answer_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a kind, concise tutor giving feedback to a student who just got a "
    "quiz question wrong. Keep your response under 80 words. Acknowledge the "
    "attempt, briefly explain why their answer is incorrect, and explain why "
    "the correct answer is right. Do NOT just restate the answer — teach the "
    "underlying concept. Avoid emojis and avoid moralizing."
)


class _LLMClient(Protocol):
    def generate(self, prompt: str) -> str | None: ...


class GeminiClient:
    """Wraps google-genai. Uses gemini-2.5-flash by default (generous free tier)."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> str | None:
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=300,
                ),
            )
            text = resp.text
            return text.strip() if text else None
        except Exception:  # noqa: BLE001 — never let AI failures block the user
            logger.exception("Gemini feedback call failed")
            return None


# Holders so tests can swap in fakes without monkeypatching imports everywhere.
_client: _LLMClient | None = None
_session_factory = _DefaultSessionLocal


def _get_client() -> _LLMClient | None:
    global _client
    if _client is not None:
        return _client
    if not settings.AI_FEEDBACK_ENABLED or not settings.GOOGLE_API_KEY:
        return None
    _client = GeminiClient(api_key=settings.GOOGLE_API_KEY, model=settings.GEMINI_MODEL)
    return _client


def set_client_for_testing(client: _LLMClient | None) -> None:
    """Swap the LLM client (used by tests). Pass None to revert to defaults."""
    global _client
    _client = client


def set_session_factory_for_testing(factory) -> None:
    """Swap the DB session factory the background task uses (for tests)."""
    global _session_factory
    _session_factory = factory or _DefaultSessionLocal


def _build_prompt(question: Question, student_answer_text: str | None) -> str:
    correct = correct_answer_text(question) or "(answer key not available)"
    return (
        f"Question: {question.text}\n"
        f"The student answered: {student_answer_text or '(no answer)'}\n"
        f"The correct answer is: {correct}\n"
        f"Existing teacher's note (may be empty): {question.explanation or ''}\n"
        "Please write the feedback now."
    )


def _resolve_student_answer_text(answer: Answer, question: Question) -> str | None:
    if answer.text_answer:
        return answer.text_answer
    if answer.selected_option_id:
        for opt in question.options:
            if opt.id == answer.selected_option_id:
                return opt.text
    return None


def generate_feedback_for_answer(answer_id: uuid.UUID) -> None:
    """Background task entry point — opens its own DB session."""
    client = _get_client()
    if client is None:
        return

    db = _session_factory()
    try:
        answer = db.get(Answer, answer_id)
        if answer is None or answer.is_correct or answer.ai_feedback:
            return
        question = db.get(Question, answer.question_id)
        if question is None:
            return
        prompt = _build_prompt(question, _resolve_student_answer_text(answer, question))
        feedback = client.generate(prompt)
        if feedback:
            answer.ai_feedback = feedback
            db.commit()
    finally:
        db.close()
