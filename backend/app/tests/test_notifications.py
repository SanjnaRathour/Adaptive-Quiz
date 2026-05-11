from fastapi.testclient import TestClient

from app.tests.helpers import (
    API,
    auth_headers,
    make_mcq_payload,
    student_token,
    teacher_token,
)


def test_publishing_quiz_notifies_students(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s1 = auth_headers(student_token(client, email="s1@example.com"))
    s2 = auth_headers(student_token(client, email="s2@example.com"))

    quiz = client.post(
        f"{API}/quizzes", json={"title": "Algebra", "subject": "Math"}, headers=t
    ).json()
    client.post(
        f"{API}/quizzes/{quiz['id']}/questions", json=make_mcq_payload(), headers=t
    )
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)

    n1 = client.get(f"{API}/notifications", headers=s1).json()
    n2 = client.get(f"{API}/notifications", headers=s2).json()
    assert n1["total"] == 1 and n1["items"][0]["type"] == "QUIZ_PUBLISHED"
    assert n1["items"][0]["related_quiz_id"] == quiz["id"]
    assert n1["unread_count"] == 1
    assert n2["total"] == 1


def test_completing_attempt_creates_result_notification(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "Algebra", "subject": "Math"}, headers=t
    ).json()
    q = client.post(
        f"{API}/quizzes/{quiz['id']}/questions", json=make_mcq_payload(), headers=t
    ).json()
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)
    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    correct = next(o for o in q["options"] if o["is_correct"])
    client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={"question_id": q["id"], "selected_option_id": correct["id"]},
        headers=s,
    )
    client.post(f"{API}/attempts/{attempt['id']}/complete", headers=s)

    body = client.get(f"{API}/notifications", headers=s).json()
    types = {n["type"] for n in body["items"]}
    assert "QUIZ_PUBLISHED" in types
    assert "QUIZ_RESULT" in types
    result = next(n for n in body["items"] if n["type"] == "QUIZ_RESULT")
    assert "100" in result["message"]


def test_unread_only_filter(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=t
    ).json()
    client.post(
        f"{API}/quizzes/{quiz['id']}/questions", json=make_mcq_payload(), headers=t
    )
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)

    body = client.get(f"{API}/notifications", headers=s).json()
    nid = body["items"][0]["id"]
    client.post(f"{API}/notifications/{nid}/read", headers=s)

    unread = client.get(
        f"{API}/notifications?unread_only=true", headers=s
    ).json()
    assert all(n["id"] != nid for n in unread["items"])
    assert unread["unread_count"] == 0


def test_user_cannot_read_someone_elses_notification(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s1 = auth_headers(student_token(client, email="s1@example.com"))
    s2 = auth_headers(student_token(client, email="s2@example.com"))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=t
    ).json()
    client.post(
        f"{API}/quizzes/{quiz['id']}/questions", json=make_mcq_payload(), headers=t
    )
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)

    s1_notifs = client.get(f"{API}/notifications", headers=s1).json()
    s1_nid = s1_notifs["items"][0]["id"]
    resp = client.post(f"{API}/notifications/{s1_nid}/read", headers=s2)
    assert resp.status_code == 404


def test_mark_all_read_clears_unread(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s1 = auth_headers(student_token(client, email="s1@example.com"))
    s2 = auth_headers(student_token(client, email="s2@example.com"))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=t
    ).json()
    client.post(
        f"{API}/quizzes/{quiz['id']}/questions", json=make_mcq_payload(), headers=t
    )
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)
    quiz2 = client.post(
        f"{API}/quizzes", json={"title": "Y", "subject": "Z"}, headers=t
    ).json()
    client.post(
        f"{API}/quizzes/{quiz2['id']}/questions", json=make_mcq_payload(), headers=t
    )
    client.post(f"{API}/quizzes/{quiz2['id']}/publish", headers=t)

    # s1 has 2 unread.
    before = client.get(f"{API}/notifications", headers=s1).json()
    assert before["unread_count"] == 2

    resp = client.post(f"{API}/notifications/read-all", headers=s1)
    assert resp.status_code == 200
    assert resp.json() == 2

    after = client.get(f"{API}/notifications", headers=s1).json()
    assert after["unread_count"] == 0
    # s2 untouched.
    other = client.get(f"{API}/notifications", headers=s2).json()
    assert other["unread_count"] == 2


def test_republishing_does_not_double_notify(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=t
    ).json()
    client.post(
        f"{API}/quizzes/{quiz['id']}/questions", json=make_mcq_payload(), headers=t
    )
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)
    notifs = client.get(f"{API}/notifications", headers=s).json()
    assert (
        len([n for n in notifs["items"] if n["related_quiz_id"] == quiz["id"]]) == 1
    )
