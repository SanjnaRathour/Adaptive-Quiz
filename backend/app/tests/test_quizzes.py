from fastapi.testclient import TestClient

from app.tests.helpers import (
    API,
    auth_headers,
    make_mcq_payload,
    student_token,
    teacher_token,
)


def _create_quiz(client: TestClient, headers: dict, **overrides) -> dict:
    body = {"title": "Algebra 101", "subject": "Math"} | overrides
    return client.post(f"{API}/quizzes", json=body, headers=headers).json()


def test_teacher_can_create_quiz(client: TestClient) -> None:
    headers = auth_headers(teacher_token(client))
    resp = client.post(
        f"{API}/quizzes",
        json={"title": "Algebra 101", "subject": "Math", "duration_minutes": 20},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Algebra 101"
    assert body["is_published"] is False
    assert body["question_count"] == 0


def test_student_cannot_create_quiz(client: TestClient) -> None:
    headers = auth_headers(student_token(client))
    resp = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=headers
    )
    assert resp.status_code == 403


def test_unpublished_quiz_hidden_from_students(client: TestClient) -> None:
    t_headers = auth_headers(teacher_token(client))
    quiz = _create_quiz(client, t_headers)
    s_headers = auth_headers(student_token(client))
    listing = client.get(f"{API}/quizzes", headers=s_headers).json()
    assert all(q["id"] != quiz["id"] for q in listing)


def test_published_quiz_visible_to_students(client: TestClient) -> None:
    t_headers = auth_headers(teacher_token(client))
    quiz = _create_quiz(client, t_headers)
    client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(),
        headers=t_headers,
    )
    publish = client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t_headers)
    assert publish.status_code == 200

    s_headers = auth_headers(student_token(client))
    listing = client.get(f"{API}/quizzes", headers=s_headers).json()
    assert any(q["id"] == quiz["id"] for q in listing)


def test_cannot_publish_empty_quiz(client: TestClient) -> None:
    headers = auth_headers(teacher_token(client))
    quiz = _create_quiz(client, headers)
    resp = client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=headers)
    assert resp.status_code == 400


def test_teacher_cannot_edit_other_teachers_quiz(client: TestClient) -> None:
    t1 = auth_headers(teacher_token(client, email="t1@example.com"))
    t2 = auth_headers(teacher_token(client, email="t2@example.com"))
    quiz = _create_quiz(client, t1)
    resp = client.patch(
        f"{API}/quizzes/{quiz['id']}", json={"title": "hijack"}, headers=t2
    )
    assert resp.status_code == 403


def test_question_creation_validates_options(client: TestClient) -> None:
    headers = auth_headers(teacher_token(client))
    quiz = _create_quiz(client, headers)
    bad = {
        "text": "Pick one",
        "type": "MULTIPLE_CHOICE",
        "difficulty": "EASY",
        "options": [
            {"text": "A", "is_correct": False, "order_index": 0},
            {"text": "B", "is_correct": False, "order_index": 1},
        ],
    }
    resp = client.post(f"{API}/quizzes/{quiz['id']}/questions", json=bad, headers=headers)
    assert resp.status_code == 422  # no correct option


def test_short_answer_requires_correct_text(client: TestClient) -> None:
    headers = auth_headers(teacher_token(client))
    quiz = _create_quiz(client, headers)
    bad = {
        "text": "Capital of France?",
        "type": "SHORT_ANSWER",
        "difficulty": "EASY",
    }
    resp = client.post(f"{API}/quizzes/{quiz['id']}/questions", json=bad, headers=headers)
    assert resp.status_code == 422


def test_question_count_reflects_added_questions(client: TestClient) -> None:
    headers = auth_headers(teacher_token(client))
    quiz = _create_quiz(client, headers)
    for i in range(3):
        client.post(
            f"{API}/quizzes/{quiz['id']}/questions",
            json=make_mcq_payload(text=f"Q{i}"),
            headers=headers,
        )
    detail = client.get(f"{API}/quizzes/{quiz['id']}", headers=headers).json()
    assert detail["question_count"] == 3


def test_delete_quiz_cascades_questions(client: TestClient) -> None:
    headers = auth_headers(teacher_token(client))
    quiz = _create_quiz(client, headers)
    client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(),
        headers=headers,
    )
    resp = client.delete(f"{API}/quizzes/{quiz['id']}", headers=headers)
    assert resp.status_code == 204
    not_found = client.get(f"{API}/quizzes/{quiz['id']}", headers=headers)
    assert not_found.status_code == 404
