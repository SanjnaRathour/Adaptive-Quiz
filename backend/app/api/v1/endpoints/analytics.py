import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_student, require_teacher
from app.core.database import get_db
from app.models.user import User
from app.schemas.analytics import (
    QuizAnalytics,
    StudentDashboard,
    TeacherOverview,
)
from app.services import analytics as analytics_svc
from app.services import quiz as quiz_svc

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/me", response_model=StudentDashboard)
def my_dashboard(
    db: Session = Depends(get_db),
    student: User = Depends(require_student),
) -> StudentDashboard:
    return analytics_svc.student_dashboard(db, student)


@router.get("/overview", response_model=TeacherOverview)
def teacher_overview(
    db: Session = Depends(get_db),
    teacher: User = Depends(require_teacher),
) -> TeacherOverview:
    return analytics_svc.teacher_overview(db, teacher)


@router.get("/quizzes/{quiz_id}", response_model=QuizAnalytics)
def quiz_analytics(
    quiz_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QuizAnalytics:
    quiz = quiz_svc.get_quiz(db, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if not quiz_svc.user_can_edit_quiz(quiz, user):
        # Only the quiz author (or admins) can see per-quiz analytics.
        raise HTTPException(status_code=403, detail="Not your quiz")
    return analytics_svc.quiz_analytics(db, quiz)
