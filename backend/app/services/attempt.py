import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.attempt import Answer, AttemptQuestion, AttemptStatus, QuizAttempt
from app.models.question import Question, QuestionOption
from app.models.quiz import Quiz
from app.models.user import User
from app.schemas.attempt import AnswerSubmit, AttemptResultDetail, AttemptResults
from app.services import adaptive
from app.services.grading import correct_answer_text, grade_answer


def _snapshot_questions(db: Session, attempt: QuizAttempt) -> None:
    """Capture the current non-deleted question pool into attempt_questions.

    Called once when an attempt is created. Locks the question set: questions
    added later don't appear in this attempt; questions soft-deleted later
    are still listed here but filtered out by the `deleted_at IS NULL` join.
    """
    questions = db.scalars(
        select(Question)
        .where(
            Question.quiz_id == attempt.quiz_id,
            Question.deleted_at.is_(None),
        )
        .order_by(Question.order_index, Question.created_at)
    ).all()
    for i, q in enumerate(questions):
        db.add(
            AttemptQuestion(attempt_id=attempt.id, question_id=q.id, order_index=i)
        )


def _existing_in_progress(
    db: Session, *, student_id: uuid.UUID, quiz_id: uuid.UUID
) -> QuizAttempt | None:
    return db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.student_id == student_id,
            QuizAttempt.status == AttemptStatus.IN_PROGRESS,
        )
    )


def start_attempt(db: Session, student: User, quiz: Quiz) -> QuizAttempt:
    """Reuse an in-progress attempt if one exists, else create a new one and snapshot.

    Race-safe: relies on the partial unique index `uq_in_progress_attempt` on
    `(quiz_id, student_id) WHERE status = 'IN_PROGRESS'`. If two near-simultaneous
    requests both pass the SELECT check, one INSERT wins and the other hits the
    constraint — we catch the IntegrityError, roll back, and re-fetch the winner.
    """
    existing = _existing_in_progress(db, student_id=student.id, quiz_id=quiz.id)
    if existing:
        return existing

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        student_id=student.id,
        status=AttemptStatus.IN_PROGRESS,
        started_at=datetime.now(timezone.utc),
        ability_estimate=0.5,
    )
    db.add(attempt)
    try:
        db.flush()  # surfaces unique-constraint violation early
    except IntegrityError:
        db.rollback()
        winner = _existing_in_progress(db, student_id=student.id, quiz_id=quiz.id)
        if winner is None:
            # Extremely unlikely: constraint fired but no IN_PROGRESS row exists.
            raise
        return winner

    _snapshot_questions(db, attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def get_attempt(db: Session, attempt_id: uuid.UUID) -> QuizAttempt | None:
    return db.scalar(
        select(QuizAttempt)
        .where(QuizAttempt.id == attempt_id)
        .options(selectinload(QuizAttempt.answers))
    )


def answered_question_ids(attempt: QuizAttempt) -> set[uuid.UUID]:
    return {a.question_id for a in attempt.answers}


def _snapshot_question_ids(db: Session, attempt_id: uuid.UUID) -> set[uuid.UUID]:
    """The set of question ids that were captured into this attempt's snapshot."""
    return set(
        db.scalars(
            select(AttemptQuestion.question_id).where(
                AttemptQuestion.attempt_id == attempt_id
            )
        ).all()
    )


def _live_snapshot_questions(db: Session, attempt_id: uuid.UUID) -> list[Question]:
    """Snapshot questions that are still askable: not soft-deleted."""
    return list(
        db.scalars(
            select(Question)
            .join(AttemptQuestion, AttemptQuestion.question_id == Question.id)
            .where(
                AttemptQuestion.attempt_id == attempt_id,
                Question.deleted_at.is_(None),
            )
            .order_by(AttemptQuestion.order_index)
            .options(selectinload(Question.options))
        ).all()
    )


def next_unanswered_question(db: Session, attempt: QuizAttempt) -> Question | None:
    """Pick the next question for the given attempt.

    Pool = the attempt's snapshot ∩ non-deleted questions ∩ not already answered.
    For adaptive quizzes, uses the adaptive engine; otherwise authoring order.
    """
    answered = answered_question_ids(attempt)
    candidates = [q for q in _live_snapshot_questions(db, attempt.id) if q.id not in answered]
    if not candidates:
        return None

    quiz = db.get(Quiz, attempt.quiz_id)
    if quiz and quiz.is_adaptive:
        return adaptive.select_next_question(candidates, ability=attempt.ability_estimate)
    return candidates[0]


def total_questions(db: Session, attempt_or_quiz_id: uuid.UUID) -> int:
    """Count of questions remaining-or-answerable for an attempt's snapshot.

    Backwards-compatible signature: callers pass either an attempt id or a quiz id.
    For attempt id: counts the non-deleted snapshot. For quiz id: counts all
    non-deleted questions in the quiz.
    """
    # Try as attempt id first.
    snap_count = db.scalar(
        select(func.count(AttemptQuestion.id)).where(
            AttemptQuestion.attempt_id == attempt_or_quiz_id
        )
    )
    if snap_count and snap_count > 0:
        # It's an attempt — count the live (non-deleted) ones in the snapshot.
        return db.scalar(
            select(func.count(Question.id))
            .join(AttemptQuestion, AttemptQuestion.question_id == Question.id)
            .where(
                AttemptQuestion.attempt_id == attempt_or_quiz_id,
                Question.deleted_at.is_(None),
            )
        ) or 0
    # Fallback: treat as quiz id.
    return db.scalar(
        select(func.count(Question.id)).where(
            Question.quiz_id == attempt_or_quiz_id,
            Question.deleted_at.is_(None),
        )
    ) or 0


def submit_answer(
    db: Session,
    attempt: QuizAttempt,
    payload: AnswerSubmit,
) -> tuple[Answer, bool]:
    """Upsert an answer for one snapshot question.

    Returns ``(answer, was_new)``. If the student is re-answering a question
    they've already answered, the existing row is updated in place. The
    attempt's ability_estimate is recomputed by replaying every answer in
    creation order so it stays consistent regardless of edits.
    """
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise ValueError("attempt is not in progress")

    # The question must be in this attempt's snapshot AND not soft-deleted.
    question = db.scalar(
        select(Question)
        .join(AttemptQuestion, AttemptQuestion.question_id == Question.id)
        .where(
            Question.id == payload.question_id,
            AttemptQuestion.attempt_id == attempt.id,
            Question.deleted_at.is_(None),
        )
        .options(selectinload(Question.options))
    )
    if question is None:
        raise ValueError(
            "question does not belong to this attempt, or has been removed"
        )

    selected_option: QuestionOption | None = None
    if payload.selected_option_id is not None:
        selected_option = db.scalar(
            select(QuestionOption).where(
                QuestionOption.id == payload.selected_option_id,
                QuestionOption.question_id == question.id,
            )
        )
        if selected_option is None:
            raise ValueError("selected option does not belong to this question")

    is_correct = grade_answer(
        question,
        selected_option=selected_option,
        text_answer=payload.text_answer,
    )

    existing = db.scalar(
        select(Answer).where(
            Answer.attempt_id == attempt.id,
            Answer.question_id == question.id,
        )
    )

    if existing is not None:
        existing.selected_option_id = selected_option.id if selected_option else None
        existing.text_answer = payload.text_answer
        existing.is_correct = is_correct
        existing.time_spent_seconds = payload.time_spent_seconds
        existing.difficulty_at_answer = question.difficulty
        answer = existing
        was_new = False
    else:
        answer = Answer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_option_id=selected_option.id if selected_option else None,
            text_answer=payload.text_answer,
            is_correct=is_correct,
            time_spent_seconds=payload.time_spent_seconds,
            difficulty_at_answer=question.difficulty,
        )
        db.add(answer)
        was_new = True

    db.flush()  # make new answer queryable for the replay below

    # Recompute ability from scratch to stay consistent across re-answers.
    attempt.ability_estimate = _replay_ability(db, attempt.id)

    db.commit()
    db.refresh(answer)
    return answer, was_new


def _replay_ability(db: Session, attempt_id: uuid.UUID) -> float:
    """Replay EMA ability over all of this attempt's answers in creation order."""
    answers = db.scalars(
        select(Answer)
        .where(Answer.attempt_id == attempt_id)
        .order_by(Answer.created_at)
    ).all()
    a = 0.5
    for ans in answers:
        a = adaptive.update_ability(
            a,
            difficulty=ans.difficulty_at_answer,
            is_correct=bool(ans.is_correct),
        )
    return a


def list_attempt_questions(
    db: Session, attempt: QuizAttempt
) -> list[tuple[Question, Answer | None]]:
    """All snapshot questions (live, non-deleted) paired with the current answer."""
    questions = _live_snapshot_questions(db, attempt.id)
    answers_by_qid = {a.question_id: a for a in attempt.answers}
    return [(q, answers_by_qid.get(q.id)) for q in questions]


def list_attempts_for_student(
    db: Session,
    student: User,
    *,
    status: AttemptStatus | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[tuple[QuizAttempt, Quiz, str, str]], int]:
    """Return (rows, total). `rows` = list of (attempt, quiz, author_name, author_email).

    Returning the author's email alongside the name lets the UI disambiguate
    two teachers whose names happen to look alike.
    """
    from app.models.user import User as UserModel

    base = (
        select(QuizAttempt, Quiz, UserModel.full_name, UserModel.email)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .join(UserModel, UserModel.id == Quiz.created_by_id)
        .where(QuizAttempt.student_id == student.id)
    )
    if status is not None:
        base = base.where(QuizAttempt.status == status)
    if search:
        like = f"%{search.lower()}%"
        base = base.where(func.lower(Quiz.title).like(like))

    total = db.scalar(
        select(func.count()).select_from(base.subquery())
    ) or 0

    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    rows = db.execute(
        base.order_by(QuizAttempt.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [(a, q, name, email) for a, q, name, email in rows], total


def _scorable_questions(db: Session, attempt: QuizAttempt) -> list[Question]:
    """Snapshot questions that count toward the score.

    A question counts if it's still in the snapshot AND either:
      - not soft-deleted (still askable), OR
      - has an answer in this attempt (so the student's effort is preserved
        even if the teacher deleted the question afterwards).
    """
    answered = answered_question_ids(attempt)
    rows = db.scalars(
        select(Question)
        .join(AttemptQuestion, AttemptQuestion.question_id == Question.id)
        .where(AttemptQuestion.attempt_id == attempt.id)
        .order_by(AttemptQuestion.order_index)
        .options(selectinload(Question.options))
    ).all()
    return [q for q in rows if q.deleted_at is None or q.id in answered]


def complete_attempt(db: Session, attempt: QuizAttempt) -> QuizAttempt:
    """Compute final score from the attempt's snapshot and mark completed."""
    if attempt.status == AttemptStatus.COMPLETED:
        return attempt

    questions = _scorable_questions(db, attempt)
    total_points = sum(q.points for q in questions)

    answers_by_qid = {a.question_id: a for a in attempt.answers}
    earned = 0
    for q in questions:
        ans = answers_by_qid.get(q.id)
        if ans and ans.is_correct:
            earned += q.points

    score = round((earned / total_points) * 100, 2) if total_points else 0.0

    attempt.status = AttemptStatus.COMPLETED
    attempt.completed_at = datetime.now(timezone.utc)
    attempt.score = score
    db.commit()
    db.refresh(attempt)
    return attempt


def build_results(db: Session, attempt: QuizAttempt) -> AttemptResults:
    from app.schemas.attempt import AttemptRead

    questions = _scorable_questions(db, attempt)
    answers_by_qid = {a.question_id: a for a in attempt.answers}

    details: list[AttemptResultDetail] = []
    correct = 0
    for q in questions:
        ans = answers_by_qid.get(q.id)
        student_answer: str | None = None
        if ans:
            if ans.selected_option_id:
                opt = next((o for o in q.options if o.id == ans.selected_option_id), None)
                student_answer = opt.text if opt else None
            else:
                student_answer = ans.text_answer
            if ans.is_correct:
                correct += 1
        details.append(
            AttemptResultDetail(
                question_id=q.id,
                question_text=q.text,
                difficulty=q.difficulty,
                points=q.points,
                your_answer=student_answer,
                correct_answer=correct_answer_text(q),
                is_correct=ans.is_correct if ans else None,
                explanation=q.explanation,
                ai_feedback=ans.ai_feedback if ans else None,
            )
        )

    return AttemptResults(
        attempt=AttemptRead.model_validate(attempt),
        total_questions=len(questions),
        correct_count=correct,
        details=details,
    )
