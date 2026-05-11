"""Aggregation queries for the analytics dashboards.

Single-purpose query functions, kept dumb on purpose — each returns the data
shape its endpoint needs, no clever sharing.
"""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.attempt import Answer, AttemptStatus, QuizAttempt
from app.models.question import Difficulty, Question
from app.models.quiz import Quiz
from app.models.user import User
from app.schemas.analytics import (
    DifficultyAccuracy,
    QuestionStat,
    QuizAnalytics,
    RecentAttempt,
    ScoreBucket,
    StudentDashboard,
    TeacherOverview,
)


def student_dashboard(db: Session, student: User) -> StudentDashboard:
    status_counts = dict(
        db.execute(
            select(QuizAttempt.status, func.count(QuizAttempt.id))
            .where(QuizAttempt.student_id == student.id)
            .group_by(QuizAttempt.status)
        ).all()
    )
    completed = status_counts.get(AttemptStatus.COMPLETED, 0)
    in_progress = status_counts.get(AttemptStatus.IN_PROGRESS, 0)
    total = sum(status_counts.values())

    avg_score = db.scalar(
        select(func.avg(QuizAttempt.score)).where(
            QuizAttempt.student_id == student.id,
            QuizAttempt.status == AttemptStatus.COMPLETED,
        )
    )

    # Accuracy bucketed by difficulty.
    rows = db.execute(
        select(
            Answer.difficulty_at_answer,
            func.count(Answer.id),
            func.sum(case((Answer.is_correct.is_(True), 1), else_=0)),
        )
        .join(QuizAttempt, Answer.attempt_id == QuizAttempt.id)
        .where(QuizAttempt.student_id == student.id)
        .group_by(Answer.difficulty_at_answer)
    ).all()
    accuracy = []
    seen_difficulties = set()
    for diff, answered, correct in rows:
        seen_difficulties.add(diff)
        accuracy.append(
            DifficultyAccuracy(
                difficulty=diff,
                answered=answered,
                correct=int(correct or 0),
                accuracy=round((correct or 0) / answered, 3) if answered else 0.0,
            )
        )
    # Always include all three buckets so the UI can render a stable 3-bar chart.
    for missing in set(Difficulty) - seen_difficulties:
        accuracy.append(
            DifficultyAccuracy(difficulty=missing, answered=0, correct=0, accuracy=0.0)
        )
    accuracy.sort(key=lambda d: list(Difficulty).index(d.difficulty))

    recent_rows = db.execute(
        select(QuizAttempt, Quiz.title)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .where(QuizAttempt.student_id == student.id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(5)
    ).all()
    recent = [
        RecentAttempt(
            attempt_id=a.id,
            quiz_id=a.quiz_id,
            quiz_title=title,
            status=a.status,
            score=a.score,
            completed_at=a.completed_at,
        )
        for a, title in recent_rows
    ]

    return StudentDashboard(
        total_attempts=total,
        completed_attempts=completed,
        in_progress_attempts=in_progress,
        average_score=float(avg_score) if avg_score is not None else None,
        accuracy_by_difficulty=accuracy,
        recent_attempts=recent,
    )


_SCORE_BUCKETS: list[tuple[str, float, float]] = [
    ("0-49", 0.0, 49.999),
    ("50-69", 50.0, 69.999),
    ("70-84", 70.0, 84.999),
    ("85-100", 85.0, 100.0),
]


def quiz_analytics(db: Session, quiz: Quiz) -> QuizAnalytics:
    total = db.scalar(
        select(func.count(QuizAttempt.id)).where(QuizAttempt.quiz_id == quiz.id)
    ) or 0
    completed = db.scalar(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.status == AttemptStatus.COMPLETED,
        )
    ) or 0
    avg = db.scalar(
        select(func.avg(QuizAttempt.score)).where(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.status == AttemptStatus.COMPLETED,
        )
    )

    distribution: list[ScoreBucket] = []
    for label, lo, hi in _SCORE_BUCKETS:
        count = db.scalar(
            select(func.count(QuizAttempt.id)).where(
                QuizAttempt.quiz_id == quiz.id,
                QuizAttempt.status == AttemptStatus.COMPLETED,
                QuizAttempt.score >= lo,
                QuizAttempt.score <= hi,
            )
        ) or 0
        distribution.append(ScoreBucket(label=label, count=count))

    rows = db.execute(
        select(
            Question.id,
            Question.text,
            Question.difficulty,
            func.count(Answer.id),
            func.sum(case((Answer.is_correct.is_(True), 1), else_=0)),
        )
        .outerjoin(Answer, Answer.question_id == Question.id)
        .where(Question.quiz_id == quiz.id, Question.deleted_at.is_(None))
        .group_by(Question.id)
        .order_by(Question.order_index, Question.created_at)
    ).all()
    question_stats = [
        QuestionStat(
            question_id=qid,
            question_text=qtext,
            difficulty=qdiff,
            times_answered=answered or 0,
            times_correct=int(correct or 0),
            accuracy=round((correct or 0) / answered, 3) if answered else 0.0,
        )
        for qid, qtext, qdiff, answered, correct in rows
    ]

    return QuizAnalytics(
        quiz_id=quiz.id,
        title=quiz.title,
        total_attempts=total,
        completed_attempts=completed,
        average_score=float(avg) if avg is not None else None,
        score_distribution=distribution,
        question_stats=question_stats,
    )


def teacher_overview(db: Session, teacher: User) -> TeacherOverview:
    authored = db.scalar(
        select(func.count(Quiz.id)).where(Quiz.created_by_id == teacher.id)
    ) or 0
    published = db.scalar(
        select(func.count(Quiz.id)).where(
            Quiz.created_by_id == teacher.id, Quiz.is_published.is_(True)
        )
    ) or 0
    total_attempts = db.scalar(
        select(func.count(QuizAttempt.id))
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .where(Quiz.created_by_id == teacher.id)
    ) or 0
    avg = db.scalar(
        select(func.avg(QuizAttempt.score))
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .where(
            Quiz.created_by_id == teacher.id,
            QuizAttempt.status == AttemptStatus.COMPLETED,
        )
    )
    return TeacherOverview(
        quizzes_authored=authored,
        quizzes_published=published,
        total_student_attempts=total_attempts,
        average_score_across_quizzes=float(avg) if avg is not None else None,
    )
