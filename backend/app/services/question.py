import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.question import Question, QuestionOption
from app.models.quiz import Quiz
from app.schemas.question import QuestionCreate, QuestionUpdate


def add_question(db: Session, quiz: Quiz, payload: QuestionCreate) -> Question:
    data = payload.model_dump(exclude={"options"})
    question = Question(quiz_id=quiz.id, **data)
    for opt in payload.options:
        question.options.append(
            QuestionOption(
                text=opt.text,
                is_correct=opt.is_correct,
                order_index=opt.order_index,
            )
        )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def get_question(db: Session, question_id: uuid.UUID) -> Question | None:
    """Return the question even if soft-deleted (callers may need it for history)."""
    return db.get(Question, question_id)


def get_active_question(db: Session, question_id: uuid.UUID) -> Question | None:
    """Return the question only if it hasn't been soft-deleted."""
    q = db.get(Question, question_id)
    if q is None or q.deleted_at is not None:
        return None
    return q


def update_question(db: Session, question: Question, payload: QuestionUpdate) -> Question:
    if question.deleted_at is not None:
        raise ValueError("question has been deleted")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    db.commit()
    db.refresh(question)
    return question


def soft_delete_question(db: Session, question: Question) -> None:
    """Mark the question deleted but keep the row so historical attempts and
    answers still resolve. Idempotent.
    """
    if question.deleted_at is None:
        question.deleted_at = datetime.now(timezone.utc)
        db.commit()
