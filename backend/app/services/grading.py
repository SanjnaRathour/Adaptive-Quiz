"""Pure grading logic — given a question and a submitted answer, decide is_correct.

Kept pure (no DB writes) so it's easy to unit test and reuse from the adaptive engine.
"""
from app.models.question import Question, QuestionOption, QuestionType


def grade_answer(
    question: Question,
    *,
    selected_option: QuestionOption | None,
    text_answer: str | None,
) -> bool:
    if question.type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
        return selected_option is not None and selected_option.is_correct
    if question.type == QuestionType.SHORT_ANSWER:
        if not text_answer or not question.correct_text_answer:
            return False
        return text_answer.strip().lower() == question.correct_text_answer.strip().lower()
    return False


def correct_answer_text(question: Question) -> str | None:
    """Human-readable correct-answer for the results view."""
    if question.type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
        for opt in question.options:
            if opt.is_correct:
                return opt.text
        return None
    return question.correct_text_answer
