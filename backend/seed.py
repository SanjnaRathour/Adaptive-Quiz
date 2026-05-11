"""Seed demo data for local testing.

Creates idempotently:
  - one teacher account: teacher@demo.com / demopass123
  - one student account: student@demo.com / demopass123
  - three published quizzes (Biology, Geography, Algebra) with mixed-difficulty
    questions covering all three question types
  - a completed sample attempt by the student so the dashboards have data

Usage:
    .venv/bin/python seed.py             # create / refresh demo data
    .venv/bin/python seed.py --reset     # wipe demo accounts first, then seed
                                         # (only touches the demo emails)

Re-running without --reset is safe: existing rows are detected and skipped.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.attempt import AttemptStatus, QuizAttempt
from app.models.quiz import Quiz
from app.models.user import User, UserRole
from app.schemas.attempt import AnswerSubmit
from app.schemas.question import (
    Difficulty,
    QuestionCreate,
    QuestionOptionCreate,
    QuestionType,
)
from app.schemas.quiz import QuizCreate
from app.schemas.user import UserCreate
from app.services import attempt as attempt_svc
from app.services import question as question_svc
from app.services import quiz as quiz_svc
from app.services import user as user_svc

TEACHER_EMAIL = "teacher@demo.com"
STUDENT_EMAIL = "student@demo.com"
DEMO_PASSWORD = "demopass123"


# --- Question builders -----------------------------------------------------


def _mcq(
    text: str,
    correct: str,
    others: tuple[str, ...],
    *,
    difficulty: str = "EASY",
    explanation: str | None = None,
    points: int = 1,
) -> QuestionCreate:
    options = [QuestionOptionCreate(text=correct, is_correct=True, order_index=0)]
    for i, t in enumerate(others, start=1):
        options.append(QuestionOptionCreate(text=t, is_correct=False, order_index=i))
    return QuestionCreate(
        text=text,
        type=QuestionType.MULTIPLE_CHOICE,
        difficulty=Difficulty[difficulty],
        explanation=explanation,
        points=points,
        options=options,
    )


def _tf(
    text: str,
    answer: bool,
    *,
    difficulty: str = "EASY",
    explanation: str | None = None,
) -> QuestionCreate:
    return QuestionCreate(
        text=text,
        type=QuestionType.TRUE_FALSE,
        difficulty=Difficulty[difficulty],
        explanation=explanation,
        options=[
            QuestionOptionCreate(text="True", is_correct=answer is True, order_index=0),
            QuestionOptionCreate(text="False", is_correct=answer is False, order_index=1),
        ],
    )


def _short(
    text: str,
    answer: str,
    *,
    difficulty: str = "MEDIUM",
    explanation: str | None = None,
) -> QuestionCreate:
    return QuestionCreate(
        text=text,
        type=QuestionType.SHORT_ANSWER,
        difficulty=Difficulty[difficulty],
        explanation=explanation,
        correct_text_answer=answer,
        options=[],
    )


# --- Quiz definitions ------------------------------------------------------


BIOLOGY = (
    QuizCreate(
        title="Fundamentals of Biology Quiz",
        description=(
            "Test your understanding of basic biology concepts including cells, "
            "genetics, human body systems, and ecosystems. Suitable for middle "
            "and high school students."
        ),
        subject="Biology",
        is_adaptive=True,
        duration_minutes=30,
        passing_score=60,
    ),
    [
        _mcq(
            "What is the primary function of red blood cells in the human body?",
            correct="Oxygen transport",
            others=("Fighting infections", "Blood clotting", "Producing hormones"),
            difficulty="EASY",
            explanation=(
                "Red blood cells carry oxygen from the lungs to body tissues "
                "via the protein hemoglobin."
            ),
        ),
        _mcq(
            "Which organelle is known as the 'powerhouse of the cell'?",
            correct="Mitochondria",
            others=("Nucleus", "Ribosome", "Golgi apparatus"),
            difficulty="EASY",
            explanation=(
                "Mitochondria generate ATP through cellular respiration, the "
                "main energy currency of the cell."
            ),
        ),
        _mcq(
            "In a eukaryotic cell, where is the majority of DNA located?",
            correct="Nucleus",
            others=("Cytoplasm", "Mitochondria only", "Cell membrane"),
            difficulty="MEDIUM",
            explanation=(
                "Most eukaryotic DNA is packaged into chromosomes inside the "
                "nucleus; a small amount also resides in mitochondria."
            ),
        ),
        _tf(
            "Humans typically have 23 pairs of chromosomes.",
            answer=True,
            difficulty="MEDIUM",
            explanation="22 autosomal pairs plus one pair of sex chromosomes.",
        ),
        _mcq(
            "Photosynthesis primarily converts which inputs into glucose?",
            correct="Carbon dioxide and water (using sunlight)",
            others=(
                "Oxygen and glucose",
                "Nitrogen and water",
                "Methane and sunlight",
            ),
            difficulty="MEDIUM",
            explanation=(
                "6 CO2 + 6 H2O + light → C6H12O6 + 6 O2. Sunlight is the energy "
                "input, captured by chlorophyll."
            ),
        ),
        _mcq(
            "Which biome is characterised by permanently frozen subsoil (permafrost)?",
            correct="Tundra",
            others=("Taiga", "Savanna", "Temperate deciduous forest"),
            difficulty="HARD",
            explanation=(
                "Tundra biomes have low temperatures year-round and a layer of "
                "permafrost beneath the active soil layer."
            ),
            points=2,
        ),
        _short(
            "Name the molecule that carries hereditary information in living cells.",
            answer="DNA",
            difficulty="HARD",
            explanation="Deoxyribonucleic acid encodes the instructions for life.",
        ),
        _mcq(
            "What process produces gametes (sperm and egg cells)?",
            correct="Meiosis",
            others=("Mitosis", "Binary fission", "Cytokinesis"),
            difficulty="HARD",
            explanation=(
                "Meiosis halves chromosome number through two successive divisions, "
                "producing four genetically distinct gametes."
            ),
            points=2,
        ),
    ],
)


GEOGRAPHY = (
    QuizCreate(
        title="World Capitals",
        description="Quick warm-up quiz on capital cities across the globe.",
        subject="Geography",
        is_adaptive=True,
        duration_minutes=15,
        passing_score=70,
    ),
    [
        _mcq(
            "What is the capital of France?",
            correct="Paris",
            others=("Lyon", "Marseille", "Bordeaux"),
            difficulty="EASY",
        ),
        _mcq(
            "What is the capital of Japan?",
            correct="Tokyo",
            others=("Kyoto", "Osaka", "Sapporo"),
            difficulty="EASY",
        ),
        _mcq(
            "What is the capital of Australia?",
            correct="Canberra",
            others=("Sydney", "Melbourne", "Perth"),
            difficulty="MEDIUM",
            explanation=(
                "Sydney and Melbourne are bigger, but Canberra was chosen as a "
                "compromise capital in 1908."
            ),
        ),
        _mcq(
            "What is the capital of Brazil?",
            correct="Brasília",
            others=("Rio de Janeiro", "São Paulo", "Salvador"),
            difficulty="MEDIUM",
            explanation=(
                "Brasília was purpose-built and replaced Rio de Janeiro as the "
                "capital in 1960."
            ),
        ),
        _short(
            "What is the capital of Bhutan?",
            answer="Thimphu",
            difficulty="HARD",
        ),
        _mcq(
            "Which is the capital of Kazakhstan?",
            correct="Astana",
            others=("Almaty", "Tashkent", "Bishkek"),
            difficulty="HARD",
            explanation=(
                "Renamed Nur-Sultan from 2019–2022, then changed back to Astana."
            ),
            points=2,
        ),
    ],
)


ALGEBRA = (
    QuizCreate(
        title="Algebra Basics",
        description=(
            "A short adaptive quiz on linear equations, slopes, and basic "
            "function composition."
        ),
        subject="Math",
        is_adaptive=True,
        duration_minutes=20,
        passing_score=60,
    ),
    [
        _mcq(
            "Solve for x:  x + 5 = 12",
            correct="7",
            others=("5", "12", "17"),
            difficulty="EASY",
        ),
        _mcq(
            "What is 3 × 7?",
            correct="21",
            others=("18", "24", "27"),
            difficulty="EASY",
        ),
        _mcq(
            "Solve for x:  2x + 4 = 14",
            correct="5",
            others=("4", "9", "10"),
            difficulty="MEDIUM",
        ),
        _mcq(
            "What is the slope of the line y = 3x + 2?",
            correct="3",
            others=("2", "−3", "1/3"),
            difficulty="MEDIUM",
            explanation=(
                "In slope-intercept form y = mx + b, the slope is m. Here m = 3."
            ),
        ),
        _mcq(
            "If f(x) = 2x + 1, what is f(f(2))?",
            correct="11",
            others=("5", "9", "13"),
            difficulty="HARD",
            explanation="f(2) = 5. Then f(5) = 2·5 + 1 = 11.",
            points=2,
        ),
        _short(
            "Solve for x:  x² − 5x + 6 = 0  (smaller root first, separated by a comma)",
            answer="2, 3",
            difficulty="HARD",
            explanation="Factor as (x−2)(x−3) = 0, giving x = 2 and x = 3.",
        ),
    ],
)


QUIZZES = [BIOLOGY, GEOGRAPHY, ALGEBRA]


# --- Seed operations -------------------------------------------------------


def upsert_user(db, *, email: str, password: str, full_name: str, role: UserRole) -> User:
    existing = user_svc.get_user_by_email(db, email)
    if existing:
        print(f"  • user {email} already exists (skipping)")
        return existing
    user = user_svc.create_user(
        db,
        UserCreate(email=email, password=password, full_name=full_name, role=role),
    )
    print(f"  + created {role.value.lower()}: {email}")
    return user


def upsert_quiz(
    db,
    teacher: User,
    meta: QuizCreate,
    questions: list[QuestionCreate],
) -> Quiz:
    existing = db.scalar(
        select(Quiz).where(
            Quiz.title == meta.title,
            Quiz.created_by_id == teacher.id,
        )
    )
    if existing:
        print(f"  • quiz '{meta.title}' already exists (skipping)")
        return existing

    quiz = quiz_svc.create_quiz(db, teacher, meta)
    for q_payload in questions:
        question_svc.add_question(db, quiz, q_payload)
    quiz_svc.publish_quiz(db, quiz)
    print(
        f"  + created and published '{meta.title}' "
        f"with {len(questions)} questions"
    )
    return quiz


def simulate_attempt(
    db,
    student: User,
    quiz: Quiz,
    *,
    answer_correctly: list[bool],
) -> QuizAttempt:
    """Walk the student through the quiz answering correct/wrong per the pattern,
    then complete it. Idempotent: if the student has already finished this quiz,
    skip.
    """
    finished = db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz.id,
            QuizAttempt.student_id == student.id,
            QuizAttempt.status == AttemptStatus.COMPLETED,
        )
    )
    if finished:
        print(f"  • student already finished '{quiz.title}' (skipping replay)")
        return finished

    attempt = attempt_svc.start_attempt(db, student, quiz)
    pattern = list(answer_correctly)
    while True:
        nq = attempt_svc.next_unanswered_question(db, attempt)
        if nq is None:
            break
        want_correct = pattern.pop(0) if pattern else True
        # Build answer payload.
        if nq.options:
            target = next(
                o for o in nq.options if (o.is_correct if want_correct else not o.is_correct)
            )
            payload = AnswerSubmit(question_id=nq.id, selected_option_id=target.id)
        else:
            # Short-answer: correct text or deliberate gibberish.
            text = nq.correct_text_answer if want_correct else "wrong-answer"
            payload = AnswerSubmit(question_id=nq.id, text_answer=text)
        attempt_svc.submit_answer(db, attempt, payload)

    attempt = attempt_svc.complete_attempt(db, attempt)
    print(
        f"  + simulated student attempt on '{quiz.title}' → score {attempt.score}%"
    )
    return attempt


def reset_demo(db) -> None:
    """Wipe demo users (cascade-deletes their quizzes, attempts, answers, notifications)."""
    for email in (TEACHER_EMAIL, STUDENT_EMAIL):
        u = user_svc.get_user_by_email(db, email)
        if u:
            db.delete(u)
            print(f"  - deleted {email} and owned data (cascade)")
    db.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete demo accounts (and their data) before seeding.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            print("Resetting demo data:")
            reset_demo(db)

        print("Seeding demo data:")
        teacher = upsert_user(
            db,
            email=TEACHER_EMAIL,
            password=DEMO_PASSWORD,
            full_name="Demo Teacher",
            role=UserRole.TEACHER,
        )
        student = upsert_user(
            db,
            email=STUDENT_EMAIL,
            password=DEMO_PASSWORD,
            full_name="Demo Student",
            role=UserRole.STUDENT,
        )

        quizzes = [upsert_quiz(db, teacher, meta, questions) for meta, questions in QUIZZES]

        # 6 of 8 correct on Biology → ~75% score.
        biology_pattern = [True, True, True, False, True, True, True, False]
        simulate_attempt(db, student, quizzes[0], answer_correctly=biology_pattern)

        print()
        print("Demo accounts ready:")
        print(f"  Teacher: {TEACHER_EMAIL}  /  {DEMO_PASSWORD}")
        print(f"  Student: {STUDENT_EMAIL}  /  {DEMO_PASSWORD}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
