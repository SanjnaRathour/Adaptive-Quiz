import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.question import Question
from app.models.quiz import Quiz
from app.models.user import User, UserRole
from app.schemas.quiz import QuizCreate, QuizUpdate


def create_quiz(db: Session, owner: User, payload: QuizCreate) -> Quiz:
    quiz = Quiz(
        **payload.model_dump(exclude_unset=False),
        created_by_id=owner.id,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


def get_quiz(db: Session, quiz_id: uuid.UUID, *, with_questions: bool = False) -> Quiz | None:
    stmt = select(Quiz).where(Quiz.id == quiz_id)
    if with_questions:
        stmt = stmt.options(selectinload(Quiz.questions).selectinload(Question.options))
    return db.scalar(stmt)


def list_quizzes_for_user(db: Session, user: User) -> list[tuple[Quiz, int]]:
    """Teachers see their own quizzes; students see only published quizzes.

    Returns (quiz, question_count) tuples. Soft-deleted questions don't count.
    """
    stmt = (
        select(Quiz, func.count(Question.id).label("question_count"))
        .outerjoin(
            Question,
            (Question.quiz_id == Quiz.id) & (Question.deleted_at.is_(None)),
        )
        .group_by(Quiz.id)
        .order_by(Quiz.created_at.desc())
    )
    if user.role == UserRole.STUDENT:
        stmt = stmt.where(Quiz.is_published.is_(True))
    elif user.role == UserRole.TEACHER:
        stmt = stmt.where(Quiz.created_by_id == user.id)
    # ADMIN sees everything.
    return [(quiz, count) for quiz, count in db.execute(stmt).all()]


def user_can_view_quiz(quiz: Quiz, user: User) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.TEACHER:
        return quiz.created_by_id == user.id
    return quiz.is_published  # STUDENT


def user_can_edit_quiz(quiz: Quiz, user: User) -> bool:
    return user.role == UserRole.ADMIN or (
        user.role == UserRole.TEACHER and quiz.created_by_id == user.id
    )


def update_quiz(db: Session, quiz: Quiz, payload: QuizUpdate) -> Quiz:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(quiz, field, value)
    db.commit()
    db.refresh(quiz)
    return quiz


def delete_quiz(db: Session, quiz: Quiz) -> None:
    db.delete(quiz)
    db.commit()


def publish_quiz(db: Session, quiz: Quiz) -> Quiz:
    quiz.is_published = True
    db.commit()
    db.refresh(quiz)
    return quiz


def count_questions(db: Session, quiz_id: uuid.UUID) -> int:
    """Count of non-deleted questions on a quiz."""
    return db.scalar(
        select(func.count(Question.id)).where(
            Question.quiz_id == quiz_id, Question.deleted_at.is_(None)
        )
    ) or 0
