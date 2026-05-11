import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuizBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    subject: str = Field(min_length=1, max_length=100)
    is_adaptive: bool = True
    duration_minutes: int = Field(default=30, ge=1, le=600)
    passing_score: int = Field(default=60, ge=0, le=100)
    scheduled_at: datetime | None = None


class QuizCreate(QuizBase):
    pass


class QuizUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=100)
    is_adaptive: bool | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    passing_score: int | None = Field(default=None, ge=0, le=100)
    scheduled_at: datetime | None = None


class QuizSummary(QuizBase):
    """Quiz metadata only — no questions."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_by_id: uuid.UUID
    is_published: bool
    created_at: datetime
    updated_at: datetime
    question_count: int = 0
