import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationRead, PaginatedNotifications
from app.services import notification as notification_svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=PaginatedNotifications,
    summary="List notifications for the current user",
    description=(
        "Paginated. `unread_only=true` filters to unread items. The "
        "`unread_count` field is always the global unread total for this "
        "user, regardless of pagination — the bell badge can read it "
        "directly without re-querying."
    ),
)
def list_my_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedNotifications:
    items, total, unread_count = notification_svc.list_for_user(
        db, user, unread_only=unread_only, page=page, page_size=page_size
    )
    return PaginatedNotifications(
        items=[NotificationRead.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationRead:
    n = notification_svc.get_for_user(db, notification_id, user)
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationRead.model_validate(notification_svc.mark_read(db, n))


@router.post(
    "/read-all",
    response_model=int,
    summary="Mark every unread notification for the current user as read",
    description="Returns the number of notifications that were marked read.",
)
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> int:
    return notification_svc.mark_all_read(db, user)
