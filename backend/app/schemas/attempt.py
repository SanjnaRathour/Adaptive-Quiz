import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.attempt import AttemptStatus
from app.models.question import Difficulty
from app.schemas.question import QuestionStudentRead


class AttemptStart(BaseModel):
    pass


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quiz_id: uuid.UUID
    student_id: uuid.UUID
    status: AttemptStatus
    started_at: datetime | None
    completed_at: datetime | None
    score: float | None
    ability_estimate: float


class AnswerSubmit(BaseModel):
    question_id: uuid.UUID
    selected_option_id: uuid.UUID | None = None
    text_answer: str | None = None
    time_spent_seconds: int = 0


class AnswerResult(BaseModel):
    """Returned after submission — no AI feedback yet (Milestone 4 fills it in)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    is_correct: bool | None
    difficulty_at_answer: Difficulty
    ai_feedback: str | None


class NextQuestionResponse(BaseModel):
    question: QuestionStudentRead | None
    remaining: int


class AttemptResultDetail(BaseModel):
    """Per-question breakdown shown after completion (with answer key + explanation)."""

    question_id: uuid.UUID
    question_text: str
    difficulty: Difficulty
    points: int
    your_answer: str | None
    correct_answer: str | None
    is_correct: bool | None
    explanation: str | None
    ai_feedback: str | None


class AttemptResults(BaseModel):
    attempt: AttemptRead
    total_questions: int
    correct_count: int
    details: list[AttemptResultDetail]


class AttemptQuestionItem(BaseModel):
    """One snapshot question paired with the student's current answer state."""

    question: QuestionStudentRead
    selected_option_id: uuid.UUID | None
    text_answer: str | None
    is_correct: bool | None


class AttemptListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_title: str
    quiz_subject: str
    quiz_author: str  # full name of the author
    quiz_author_email: str  # disambiguates same-named teachers
    status: AttemptStatus
    score: float | None
    started_at: datetime | None
    completed_at: datetime | None


class PaginatedAttempts(BaseModel):
    items: list[AttemptListItem]
    total: int
    page: int
    page_size: int
    has_next: bool
