"""Tests for the AI feedback flow — Anthropic client is mocked."""
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.services import ai_feedback
from app.tests.helpers import (
    API,
    auth_headers,
    make_mcq_payload,
    student_token,
    teacher_token,
)


class _RecordingClient:
    def __init__(self, response: str = "Try thinking about it this way: ...") -> None:
        self.response = response
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str | None:
        self.calls.append(prompt)
        return self.response


@pytest.fixture
def fake_llm() -> Generator[_RecordingClient, None, None]:
    fake = _RecordingClient()
    ai_feedback.set_client_for_testing(fake)
    try:
        yield fake
    finally:
        ai_feedback.set_client_for_testing(None)


def _published_quiz_with_q(client: TestClient, t_headers: dict) -> tuple[dict, dict]:
    quiz = client.post(
        f"{API}/quizzes", json={"title": "T", "subject": "Math"}, headers=t_headers
    ).json()
    q = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(text="2+2?", correct="4", others=("3", "5")),
        headers=t_headers,
    ).json()
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t_headers)
    return quiz, q


def test_wrong_answer_triggers_ai_feedback(client: TestClient, fake_llm: _RecordingClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, q = _published_quiz_with_q(client, t)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    wrong_opt = next(o for o in q["options"] if not o["is_correct"])
    client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={"question_id": q["id"], "selected_option_id": wrong_opt["id"]},
        headers=s,
    )
    # BackgroundTasks run after the response; with TestClient they run before
    # the request returns inside the `with` block, so by here it's already done.
    assert len(fake_llm.calls) == 1
    assert "2+2?" in fake_llm.calls[0]
    assert "correct answer is: 4" in fake_llm.calls[0]


def test_correct_answer_does_not_trigger_ai_feedback(
    client: TestClient, fake_llm: _RecordingClient
) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, q = _published_quiz_with_q(client, t)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    correct_opt = next(o for o in q["options"] if o["is_correct"])
    client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={"question_id": q["id"], "selected_option_id": correct_opt["id"]},
        headers=s,
    )
    assert fake_llm.calls == []


def test_ai_feedback_persists_and_appears_in_results(
    client: TestClient, fake_llm: _RecordingClient
) -> None:
    fake_llm.response = "Remember: addition is commutative."
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, q = _published_quiz_with_q(client, t)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    wrong_opt = next(o for o in q["options"] if not o["is_correct"])
    client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={"question_id": q["id"], "selected_option_id": wrong_opt["id"]},
        headers=s,
    )
    client.post(f"{API}/attempts/{attempt['id']}/complete", headers=s)
    results = client.get(f"{API}/attempts/{attempt['id']}/results", headers=s).json()
    assert results["details"][0]["ai_feedback"] == "Remember: addition is commutative."


def test_adaptive_quiz_picks_easy_after_failures(
    client: TestClient, fake_llm: _RecordingClient
) -> None:
    """End-to-end: wrong answers on EASY questions should drag ability down so
    the engine keeps serving EASY (not promoting to MEDIUM/HARD)."""
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz = client.post(
        f"{API}/quizzes",
        json={"title": "Adaptive", "subject": "Math", "is_adaptive": True},
        headers=t,
    ).json()
    # Mix: 3 EASY + 3 MEDIUM + 3 HARD.
    questions: list[dict] = []
    for i in range(3):
        for diff in ("EASY", "MEDIUM", "HARD"):
            payload = make_mcq_payload(text=f"{diff}-{i}", correct="A", others=("B", "C"))
            payload["difficulty"] = diff
            qjson = client.post(
                f"{API}/quizzes/{quiz['id']}/questions", json=payload, headers=t
            ).json()
            questions.append(qjson)
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    seen_difficulties: list[str] = []
    for _ in range(5):
        nq = client.get(f"{API}/attempts/{attempt['id']}/next-question", headers=s).json()
        if nq["question"] is None:
            break
        seen_difficulties.append(nq["question"]["difficulty"])
        # Always answer wrong.
        question_id = nq["question"]["id"]
        full = next(q for q in questions if q["id"] == question_id)
        wrong_opt = next(o for o in full["options"] if not o["is_correct"])
        client.post(
            f"{API}/attempts/{attempt['id']}/answers",
            json={"question_id": question_id, "selected_option_id": wrong_opt["id"]},
            headers=s,
        )
    # First served question is MEDIUM (default ability 0.5). After wrong-on-MEDIUM
    # the ability drops below 0.4, so subsequent picks must be EASY.
    assert seen_difficulties[0] == "MEDIUM"
    assert "EASY" in seen_difficulties[1:]
