import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    related_quiz_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class PaginatedNotifications(BaseModel):
    items: list[NotificationRead]
    total: int
    page: int
    page_size: int
    has_next: bool
    unread_count: int
