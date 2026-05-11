import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.attempt import AttemptStatus
from app.models.question import Difficulty


class DifficultyAccuracy(BaseModel):
    difficulty: Difficulty
    answered: int
    correct: int
    accuracy: float  # 0.0 - 1.0


class RecentAttempt(BaseModel):
    attempt_id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    status: AttemptStatus
    score: float | None
    completed_at: datetime | None


class StudentDashboard(BaseModel):
    total_attempts: int
    completed_attempts: int
    in_progress_attempts: int
    average_score: float | None
    accuracy_by_difficulty: list[DifficultyAccuracy]
    recent_attempts: list[RecentAttempt]


class ScoreBucket(BaseModel):
    label: str  # e.g. "0-49"
    count: int


class QuestionStat(BaseModel):
    question_id: uuid.UUID
    question_text: str
    difficulty: Difficulty
    times_answered: int
    times_correct: int
    accuracy: float


class QuizAnalytics(BaseModel):
    quiz_id: uuid.UUID
    title: str
    total_attempts: int
    completed_attempts: int
    average_score: float | None
    score_distribution: list[ScoreBucket]
    question_stats: list[QuestionStat]


class TeacherOverview(BaseModel):
    quizzes_authored: int
    quizzes_published: int
    total_student_attempts: int
    average_score_across_quizzes: float | None
