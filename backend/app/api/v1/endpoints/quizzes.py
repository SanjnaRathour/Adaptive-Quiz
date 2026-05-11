import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_teacher
from app.core.database import get_db
from app.models.user import User
from app.schemas.question import (
    QuestionCreate,
    QuestionTeacherRead,
    QuestionUpdate,
)
from app.schemas.quiz import QuizCreate, QuizSummary, QuizUpdate
from app.services import notification as notification_svc
from app.services import question as question_svc
from app.services import quiz as quiz_svc

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.post("", response_model=QuizSummary, status_code=status.HTTP_201_CREATED)
def create(
    payload: QuizCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> QuizSummary:
    quiz = quiz_svc.create_quiz(db, teacher, payload)
    return QuizSummary.model_validate(quiz).model_copy(update={"question_count": 0})


@router.get("", response_model=list[QuizSummary])
def list_quizzes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[QuizSummary]:
    rows = quiz_svc.list_quizzes_for_user(db, user)
    return [
        QuizSummary.model_validate(quiz).model_copy(update={"question_count": count})
        for quiz, count in rows
    ]


def _load_quiz_or_404(db: Session, quiz_id: uuid.UUID) -> "object":
    quiz = quiz_svc.get_quiz(db, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


@router.get("/{quiz_id}", response_model=QuizSummary)
def get_one(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuizSummary:
    quiz = _load_quiz_or_404(db, quiz_id)
    if not quiz_svc.user_can_view_quiz(quiz, user):
        raise HTTPException(status_code=404, detail="Quiz not found")
    count = quiz_svc.count_questions(db, quiz_id)
    return QuizSummary.model_validate(quiz).model_copy(update={"question_count": count})


@router.patch("/{quiz_id}", response_model=QuizSummary)
def update(
    quiz_id: uuid.UUID,
    payload: QuizUpdate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> QuizSummary:
    quiz = _load_quiz_or_404(db, quiz_id)
    if not quiz_svc.user_can_edit_quiz(quiz, teacher):
        raise HTTPException(status_code=403, detail="Not your quiz")
    quiz = quiz_svc.update_quiz(db, quiz, payload)
    count = quiz_svc.count_questions(db, quiz_id)
    return QuizSummary.model_validate(quiz).model_copy(update={"question_count": count})


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> None:
    quiz = _load_quiz_or_404(db, quiz_id)
    if not quiz_svc.user_can_edit_quiz(quiz, teacher):
        raise HTTPException(status_code=403, detail="Not your quiz")
    quiz_svc.delete_quiz(db, quiz)


@router.post("/{quiz_id}/publish", response_model=QuizSummary)
def publish(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> QuizSummary:
    quiz = _load_quiz_or_404(db, quiz_id)
    if not quiz_svc.user_can_edit_quiz(quiz, teacher):
        raise HTTPException(status_code=403, detail="Not your quiz")
    if quiz_svc.count_questions(db, quiz_id) == 0:
        raise HTTPException(status_code=400, detail="Cannot publish a quiz with no questions")
    was_published = quiz.is_published
    quiz = quiz_svc.publish_quiz(db, quiz)
    if not was_published:
        notification_svc.notify_quiz_published(db, quiz)
    count = quiz_svc.count_questions(db, quiz_id)
    return QuizSummary.model_validate(quiz).model_copy(update={"question_count": count})


@router.post(
    "/{quiz_id}/questions",
    response_model=QuestionTeacherRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a question to a quiz",
    description=(
        "Allowed on draft and published quizzes. New questions only enter "
        "future attempts — students currently mid-attempt keep the question "
        "pool they were given when they started (their snapshot)."
    ),
)
def add_question(
    quiz_id: uuid.UUID,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> QuestionTeacherRead:
    quiz = _load_quiz_or_404(db, quiz_id)
    if not quiz_svc.user_can_edit_quiz(quiz, teacher):
        raise HTTPException(status_code=403, detail="Not your quiz")
    q = question_svc.add_question(db, quiz, payload)
    return QuestionTeacherRead.model_validate(q)


@router.get("/{quiz_id}/questions", response_model=list[QuestionTeacherRead])
def list_questions(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> list[QuestionTeacherRead]:
    quiz = quiz_svc.get_quiz(db, quiz_id, with_questions=True)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if not quiz_svc.user_can_edit_quiz(quiz, teacher):
        raise HTTPException(status_code=403, detail="Not your quiz")
    # Hide soft-deleted questions from the authoring UI.
    return [
        QuestionTeacherRead.model_validate(q)
        for q in quiz.questions
        if q.deleted_at is None
    ]


@router.patch("/questions/{question_id}", response_model=QuestionTeacherRead)
def update_question(
    question_id: uuid.UUID,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> QuestionTeacherRead:
    q = question_svc.get_active_question(db, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    if not quiz_svc.user_can_edit_quiz(q.quiz, teacher):
        raise HTTPException(status_code=403, detail="Not your quiz")
    try:
        q = question_svc.update_question(db, q, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionTeacherRead.model_validate(q)


@router.delete(
    "/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a question",
    description=(
        "Marks the question as deleted (sets `deleted_at`) but never removes "
        "the row. Soft-deleted questions are hidden from listings, the "
        "authoring UI, and all new attempts. They are still skipped for any "
        "in-flight attempt that had them in its snapshot, but answers a "
        "student already submitted for them are preserved in scoring and in "
        "the attempt's results view."
    ),
)
def delete_question(
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> None:
    q = question_svc.get_question(db, question_id)
    if q is None or q.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Question not found")
    if not quiz_svc.user_can_edit_quiz(q.quiz, teacher):
        raise HTTPException(status_code=403, detail="Not your quiz")
    question_svc.soft_delete_question(db, q)
