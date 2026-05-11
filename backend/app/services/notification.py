import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.quiz import Quiz
from app.models.user import User, UserRole


def _create(
    db: Session,
    *,
    user_id: uuid.UUID,
    type_: NotificationType,
    title: str,
    message: str,
    related_quiz_id: uuid.UUID | None = None,
) -> Notification:
    n = Notification(
        user_id=user_id,
        type=type_,
        title=title,
        message=message,
        related_quiz_id=related_quiz_id,
    )
    db.add(n)
    return n


def notify_quiz_published(db: Session, quiz: Quiz) -> int:
    """Broadcast a QUIZ_PUBLISHED notification to all active students.

    Returns the number of notifications created.
    """
    students = db.scalars(
        select(User).where(User.role == UserRole.STUDENT, User.is_active.is_(True))
    ).all()
    for s in students:
        _create(
            db,
            user_id=s.id,
            type_=NotificationType.QUIZ_PUBLISHED,
            title=f"New quiz: {quiz.title}",
            message=f"A new quiz on {quiz.subject} is now available.",
            related_quiz_id=quiz.id,
        )
    db.commit()
    return len(students)


def notify_attempt_completed(
    db: Session, *, student_id: uuid.UUID, quiz: Quiz, score: float | None
) -> Notification:
    score_str = f"{score:.1f}%" if score is not None else "(unscored)"
    n = _create(
        db,
        user_id=student_id,
        type_=NotificationType.QUIZ_RESULT,
        title=f"Results: {quiz.title}",
        message=f"You scored {score_str}.",
        related_quiz_id=quiz.id,
    )
    db.commit()
    db.refresh(n)
    return n


def list_for_user(
    db: Session,
    user: User,
    *,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Notification], int, int]:
    """Return (items, total_matching, total_unread).

    `total_unread` always reflects ALL unread notifications regardless of the
    page/filter so the bell badge can stay accurate.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    base = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        base = base.where(Notification.read_at.is_(None))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    unread_count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
    ) or 0
    return items, total, unread_count


def mark_read(db: Session, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, user: User) -> int:
    """Mark every unread notification for the user as read; return the count."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
    ).all()
    for n in rows:
        n.read_at = now
    if rows:
        db.commit()
    return len(rows)


def get_for_user(
    db: Session, notification_id: uuid.UUID, user: User
) -> Notification | None:
    return db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
