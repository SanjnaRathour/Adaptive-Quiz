import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.question import Difficulty, QuestionType


class QuestionOptionCreate(BaseModel):
    text: str = Field(min_length=1)
    is_correct: bool = False
    order_index: int = 0


class QuestionOptionTeacherRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    is_correct: bool
    order_index: int


class QuestionOptionStudentRead(BaseModel):
    """Student view: no `is_correct` flag exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    order_index: int


class QuestionCreate(BaseModel):
    text: str = Field(min_length=1)
    type: QuestionType = QuestionType.MULTIPLE_CHOICE
    difficulty: Difficulty = Difficulty.MEDIUM
    explanation: str | None = None
    correct_text_answer: str | None = None
    points: int = Field(default=1, ge=1, le=100)
    order_index: int = 0
    options: list[QuestionOptionCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_payload(self) -> "QuestionCreate":
        if self.type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
            if not self.options:
                raise ValueError(f"{self.type.value} questions must have options")
            if not any(o.is_correct for o in self.options):
                raise ValueError("at least one option must be marked correct")
        elif self.type == QuestionType.SHORT_ANSWER:
            if not self.correct_text_answer:
                raise ValueError("SHORT_ANSWER questions require correct_text_answer")
        return self


class QuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    difficulty: Difficulty | None = None
    explanation: str | None = None
    points: int | None = Field(default=None, ge=1, le=100)
    order_index: int | None = None


class QuestionTeacherRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quiz_id: uuid.UUID
    text: str
    type: QuestionType
    difficulty: Difficulty
    explanation: str | None
    correct_text_answer: str | None
    points: int
    order_index: int
    options: list[QuestionOptionTeacherRead]


class QuestionStudentRead(BaseModel):
    """What a student sees while taking a quiz: no answer key, no explanation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    type: QuestionType
    difficulty: Difficulty
    points: int
    options: list[QuestionOptionStudentRead]


class DifficultyHintRequest(BaseModel):
    text: str = Field(min_length=1)


class DifficultyHintResponse(BaseModel):
    difficulty: Difficulty
    ai_used: bool
