from fastapi.testclient import TestClient

from app.tests.helpers import (
    API,
    auth_headers,
    make_mcq_payload,
    student_token,
    teacher_token,
)


def _setup_taken_quiz(client: TestClient, *, n_correct: int, n_wrong: int) -> dict:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "Math", "subject": "Math"}, headers=t
    ).json()
    questions = []
    for i in range(n_correct + n_wrong):
        q = client.post(
            f"{API}/quizzes/{quiz['id']}/questions",
            json=make_mcq_payload(text=f"Q{i}", correct="A", others=("B", "C")),
            headers=t,
        ).json()
        questions.append(q)
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)
    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()

    for i, q in enumerate(questions):
        opt = next(o for o in q["options"] if o["is_correct"]) if i < n_correct else next(
            o for o in q["options"] if not o["is_correct"]
        )
        client.post(
            f"{API}/attempts/{attempt['id']}/answers",
            json={"question_id": q["id"], "selected_option_id": opt["id"]},
            headers=s,
        )
    client.post(f"{API}/attempts/{attempt['id']}/complete", headers=s)
    return {"teacher": t, "student": s, "quiz": quiz, "attempt": attempt}


def test_student_dashboard_summarizes_attempts(client: TestClient) -> None:
    ctx = _setup_taken_quiz(client, n_correct=2, n_wrong=1)
    resp = client.get(f"{API}/analytics/me", headers=ctx["student"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_attempts"] == 1
    assert body["completed_attempts"] == 1
    assert body["in_progress_attempts"] == 0
    # 2/3 ≈ 66.67%
    assert 66 < body["average_score"] < 67
    # Always 3 difficulty buckets so the UI can chart them.
    assert len(body["accuracy_by_difficulty"]) == 3
    assert len(body["recent_attempts"]) == 1


def test_teacher_overview_counts_authored_and_published(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    # 3 quizzes, only 1 published.
    ids = []
    for i in range(3):
        q = client.post(
            f"{API}/quizzes", json={"title": f"Q{i}", "subject": "S"}, headers=t
        ).json()
        ids.append(q["id"])
    client.post(
        f"{API}/quizzes/{ids[0]}/questions",
        json=make_mcq_payload(),
        headers=t,
    )
    client.post(f"{API}/quizzes/{ids[0]}/publish", headers=t)

    resp = client.get(f"{API}/analytics/overview", headers=t)
    assert resp.status_code == 200
    body = resp.json()
    assert body["quizzes_authored"] == 3
    assert body["quizzes_published"] == 1


def test_teacher_can_view_their_quiz_analytics(client: TestClient) -> None:
    ctx = _setup_taken_quiz(client, n_correct=2, n_wrong=1)
    resp = client.get(
        f"{API}/analytics/quizzes/{ctx['quiz']['id']}", headers=ctx["teacher"]
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_attempts"] == 1
    assert body["completed_attempts"] == 1
    assert len(body["question_stats"]) == 3
    # Each was answered exactly once; check at least one wrong.
    assert any(qs["times_correct"] == 0 for qs in body["question_stats"])
    # Score distribution always has 4 buckets.
    assert len(body["score_distribution"]) == 4


def test_teacher_cannot_view_other_teachers_analytics(client: TestClient) -> None:
    t1 = auth_headers(teacher_token(client, email="t1@example.com"))
    t2 = auth_headers(teacher_token(client, email="t2@example.com"))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "Mine", "subject": "Math"}, headers=t1
    ).json()
    resp = client.get(f"{API}/analytics/quizzes/{quiz['id']}", headers=t2)
    assert resp.status_code == 403


def test_student_cannot_access_teacher_endpoints(client: TestClient) -> None:
    s = auth_headers(student_token(client))
    assert client.get(f"{API}/analytics/overview", headers=s).status_code == 403
