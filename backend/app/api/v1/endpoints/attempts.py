import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_student
from app.core.database import get_db
from app.models.attempt import AttemptStatus
from app.models.user import User, UserRole
from app.schemas.attempt import (
    AnswerResult,
    AnswerSubmit,
    AttemptListItem,
    AttemptQuestionItem,
    AttemptRead,
    AttemptResults,
    NextQuestionResponse,
    PaginatedAttempts,
)
from app.schemas.question import QuestionStudentRead
from app.services import attempt as attempt_svc
from app.services import notification as notification_svc
from app.services import quiz as quiz_svc
from app.services.ai_feedback import generate_feedback_for_answer

router = APIRouter(tags=["attempts"])


@router.post(
    "/quizzes/{quiz_id}/attempts",
    response_model=AttemptRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start (or resume) an attempt",
    description=(
        "Idempotent while the student has an IN_PROGRESS attempt — returns "
        "the same attempt. Otherwise creates a new one and snapshots the "
        "current non-deleted question pool into `attempt_questions` so the "
        "set is frozen for the rest of the attempt."
    ),
)
def start_attempt(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> AttemptRead:
    quiz = quiz_svc.get_quiz(db, quiz_id)
    if quiz is None or not quiz.is_published:
        raise HTTPException(status_code=404, detail="Quiz not found or not yet published")
    if quiz_svc.count_questions(db, quiz_id) == 0:
        raise HTTPException(status_code=400, detail="This quiz has no questions yet")
    attempt = attempt_svc.start_attempt(db, student, quiz)
    return AttemptRead.model_validate(attempt)


def _load_owned_attempt(db: Session, attempt_id: uuid.UUID, user: User):
    attempt = attempt_svc.get_attempt(db, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.student_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt


@router.get(
    "/attempts",
    response_model=PaginatedAttempts,
    summary="List the current student's attempts",
    description=(
        "Paginated list of the student's own attempts, optionally filtered by "
        "status (IN_PROGRESS / COMPLETED / ABANDONED) and a case-insensitive "
        "quiz-title search."
    ),
)
def list_my_attempts(
    status_: AttemptStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> PaginatedAttempts:
    rows, total = attempt_svc.list_attempts_for_student(
        db, student, status=status_, search=search, page=page, page_size=page_size
    )
    items = [
        AttemptListItem(
            id=a.id,
            quiz_id=q.id,
            quiz_title=q.title,
            quiz_subject=q.subject,
            quiz_author=author_name,
            quiz_author_email=author_email,
            status=a.status,
            score=a.score,
            started_at=a.started_at,
            completed_at=a.completed_at,
        )
        for a, q, author_name, author_email in rows
    ]
    return PaginatedAttempts(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
    )


@router.get(
    "/attempts/{attempt_id}/questions",
    response_model=list[AttemptQuestionItem],
    summary="List all snapshot questions in this attempt with the student's current answers",
    description=(
        "Used by the take-quiz UI for free Prev/Next navigation. Returns the "
        "attempt's frozen question pool (filtered to non-deleted questions) "
        "in snapshot order, each annotated with the student's current "
        "selection and grading status (null until they answer)."
    ),
)
def list_attempt_questions(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> list[AttemptQuestionItem]:
    attempt = _load_owned_attempt(db, attempt_id, student)
    rows = attempt_svc.list_attempt_questions(db, attempt)
    return [
        AttemptQuestionItem(
            question=QuestionStudentRead.model_validate(q),
            selected_option_id=ans.selected_option_id if ans else None,
            text_answer=ans.text_answer if ans else None,
            is_correct=ans.is_correct if ans else None,
        )
        for q, ans in rows
    ]


@router.get("/attempts/{attempt_id}", response_model=AttemptRead)
def read_attempt(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptRead:
    attempt = _load_owned_attempt(db, attempt_id, user)
    return AttemptRead.model_validate(attempt)


@router.get("/attempts/{attempt_id}/next-question", response_model=NextQuestionResponse)
def next_question(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> NextQuestionResponse:
    attempt = _load_owned_attempt(db, attempt_id, student)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Attempt is not in progress")
    q = attempt_svc.next_unanswered_question(db, attempt)
    total = attempt_svc.total_questions(db, attempt.quiz_id)
    remaining = total - len(attempt_svc.answered_question_ids(attempt))
    return NextQuestionResponse(
        question=QuestionStudentRead.model_validate(q) if q else None,
        remaining=remaining,
    )


@router.post(
    "/attempts/{attempt_id}/answers",
    response_model=AnswerResult,
    status_code=status.HTTP_201_CREATED,
    summary="Submit (or update) an answer for a question in this attempt",
    description=(
        "Upsert: re-submitting for the same question updates the existing "
        "answer in place — the student is free to change their mind until "
        "the attempt is completed. Returns 400 if the question is not part "
        "of this attempt's snapshot (e.g. it was added after the attempt "
        "started, or has since been soft-deleted). The attempt's running "
        "ability estimate is recomputed from all answers in creation order. "
        "An AI feedback explanation is queued only on the FIRST wrong "
        "submission for each question — bouncing answers won't burn quota."
    ),
)
def submit_answer(
    attempt_id: uuid.UUID,
    payload: AnswerSubmit,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> AnswerResult:
    attempt = _load_owned_attempt(db, attempt_id, student)
    try:
        answer, was_new = attempt_svc.submit_answer(db, attempt, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # AI feedback is queued only the first time the student gets it wrong, so
    # bouncing between answers doesn't burn API quota.
    if was_new and answer.is_correct is False:
        background_tasks.add_task(generate_feedback_for_answer, answer.id)

    return AnswerResult.model_validate(answer)


@router.post("/attempts/{attempt_id}/complete", response_model=AttemptRead)
def complete_attempt(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> AttemptRead:
    attempt = _load_owned_attempt(db, attempt_id, student)
    was_already_done = attempt.status == AttemptStatus.COMPLETED
    attempt = attempt_svc.complete_attempt(db, attempt)
    if not was_already_done:
        quiz = quiz_svc.get_quiz(db, attempt.quiz_id)
        if quiz is not None:
            notification_svc.notify_attempt_completed(
                db, student_id=student.id, quiz=quiz, score=attempt.score
            )
    return AttemptRead.model_validate(attempt)


@router.get("/attempts/{attempt_id}/results", response_model=AttemptResults)
def attempt_results(
    attempt_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AttemptResults:
    attempt = _load_owned_attempt(db, attempt_id, user)
    if attempt.status != AttemptStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Attempt is not yet completed")
    return attempt_svc.build_results(db, attempt)
