from fastapi import APIRouter

from app.api.v1.endpoints import analytics, attempts, auth, notifications, quizzes

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(quizzes.router)
api_router.include_router(attempts.router)
api_router.include_router(analytics.router)
api_router.include_router(notifications.router)
