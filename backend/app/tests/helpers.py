"""Shared test helpers — building authenticated clients quickly."""
from fastapi.testclient import TestClient

from app.core.config import settings

API = settings.API_V1_PREFIX


def register_and_login(
    client: TestClient,
    *,
    email: str,
    password: str = "supersecret",
    role: str = "STUDENT",
    full_name: str = "User",
) -> str:
    client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": role},
    )
    resp = client.post(
        f"{API}/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def teacher_token(client: TestClient, email: str = "teacher@example.com") -> str:
    return register_and_login(client, email=email, role="TEACHER", full_name="Teacher")


def student_token(client: TestClient, email: str = "student@example.com") -> str:
    return register_and_login(client, email=email, role="STUDENT", full_name="Student")


def make_mcq_payload(
    *, text: str = "What is 2+2?", correct: str = "4", others: tuple[str, ...] = ("3", "5", "22")
) -> dict:
    options = [{"text": correct, "is_correct": True, "order_index": 0}]
    for i, t in enumerate(others, start=1):
        options.append({"text": t, "is_correct": False, "order_index": i})
    return {
        "text": text,
        "type": "MULTIPLE_CHOICE",
        "difficulty": "EASY",
        "explanation": f"because {correct}",
        "points": 1,
        "options": options,
    }
