from fastapi.testclient import TestClient

from app.tests.helpers import (
    API,
    auth_headers,
    make_mcq_payload,
    student_token,
    teacher_token,
)


def _build_published_quiz(client: TestClient, t_headers: dict, *, n_questions: int = 3) -> dict:
    quiz = client.post(
        f"{API}/quizzes", json={"title": "Math", "subject": "Math"}, headers=t_headers
    ).json()
    questions = []
    for i in range(n_questions):
        q = client.post(
            f"{API}/quizzes/{quiz['id']}/questions",
            json=make_mcq_payload(text=f"Q{i}", correct=str(i), others=("99", "100")),
            headers=t_headers,
        ).json()
        questions.append(q)
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t_headers)
    return {"quiz": quiz, "questions": questions}


def _correct_option_id(question: dict) -> str:
    # Teacher view of question — options carry is_correct.
    for o in question["options"]:
        if o["is_correct"]:
            return o["id"]
    raise AssertionError("no correct option")


def test_student_can_start_attempt(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    bundle = _build_published_quiz(client, t, n_questions=2)
    resp = client.post(f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s)
    assert resp.status_code == 201
    assert resp.json()["status"] == "IN_PROGRESS"


def test_starting_attempt_is_idempotent_while_in_progress(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    bundle = _build_published_quiz(client, t)
    a1 = client.post(f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s).json()
    a2 = client.post(f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s).json()
    assert a1["id"] == a2["id"]


def test_student_cannot_attempt_unpublished_quiz(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "Draft", "subject": "X"}, headers=t
    ).json()
    resp = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s)
    assert resp.status_code == 404


def test_full_attempt_flow_and_grading(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    bundle = _build_published_quiz(client, t, n_questions=3)

    attempt = client.post(
        f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s
    ).json()
    aid = attempt["id"]

    # Answer Q0 correctly, Q1 wrong, Q2 correctly.
    answers = [
        (bundle["questions"][0], True),
        (bundle["questions"][1], False),
        (bundle["questions"][2], True),
    ]
    for q, want_correct in answers:
        if want_correct:
            opt_id = _correct_option_id(q)
        else:
            wrong = next(o for o in q["options"] if not o["is_correct"])
            opt_id = wrong["id"]
        resp = client.post(
            f"{API}/attempts/{aid}/answers",
            json={"question_id": q["id"], "selected_option_id": opt_id},
            headers=s,
        )
        assert resp.status_code == 201
        assert resp.json()["is_correct"] is want_correct

    completed = client.post(f"{API}/attempts/{aid}/complete", headers=s).json()
    assert completed["status"] == "COMPLETED"
    # 2/3 correct → ~66.67%
    assert 66.0 < completed["score"] < 67.0


def test_re_answering_question_upserts_existing_answer(client: TestClient) -> None:
    """Re-submitting for the same question updates the prior row instead of
    rejecting. The student can change their mind until the attempt is
    completed.
    """
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    bundle = _build_published_quiz(client, t, n_questions=1)
    attempt = client.post(
        f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s
    ).json()
    q = bundle["questions"][0]
    correct_id = _correct_option_id(q)
    wrong_id = next(o["id"] for o in q["options"] if not o["is_correct"])

    first = client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={"question_id": q["id"], "selected_option_id": wrong_id},
        headers=s,
    )
    second = client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={"question_id": q["id"], "selected_option_id": correct_id},
        headers=s,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]  # same row
    assert first.json()["is_correct"] is False
    assert second.json()["is_correct"] is True

    # Score reflects the latest answer.
    completed = client.post(
        f"{API}/attempts/{attempt['id']}/complete", headers=s
    ).json()
    assert completed["score"] == 100.0


def test_results_hide_then_reveal(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    bundle = _build_published_quiz(client, t, n_questions=1)
    attempt = client.post(
        f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s
    ).json()
    # Results before completion = 400.
    early = client.get(f"{API}/attempts/{attempt['id']}/results", headers=s)
    assert early.status_code == 400

    q = bundle["questions"][0]
    client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={"question_id": q["id"], "selected_option_id": _correct_option_id(q)},
        headers=s,
    )
    client.post(f"{API}/attempts/{attempt['id']}/complete", headers=s)

    results = client.get(f"{API}/attempts/{attempt['id']}/results", headers=s).json()
    assert results["correct_count"] == 1
    assert results["details"][0]["correct_answer"] == "0"  # see make_mcq_payload defaults
    assert results["details"][0]["explanation"] is not None


def test_next_question_returns_unanswered_then_none(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    bundle = _build_published_quiz(client, t, n_questions=2)
    attempt = client.post(
        f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s
    ).json()
    aid = attempt["id"]

    nq1 = client.get(f"{API}/attempts/{aid}/next-question", headers=s).json()
    assert nq1["question"] is not None
    assert "is_correct" not in str(nq1["question"])  # answer key never leaks
    assert nq1["remaining"] == 2

    # Answer both.
    for q in bundle["questions"]:
        client.post(
            f"{API}/attempts/{aid}/answers",
            json={"question_id": q["id"], "selected_option_id": _correct_option_id(q)},
            headers=s,
        )
    nq_done = client.get(f"{API}/attempts/{aid}/next-question", headers=s).json()
    assert nq_done["question"] is None
    assert nq_done["remaining"] == 0


def test_student_cannot_view_other_students_attempt(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s1 = auth_headers(student_token(client, email="s1@example.com"))
    s2 = auth_headers(student_token(client, email="s2@example.com"))
    bundle = _build_published_quiz(client, t)
    attempt = client.post(
        f"{API}/quizzes/{bundle['quiz']['id']}/attempts", headers=s1
    ).json()
    resp = client.get(f"{API}/attempts/{attempt['id']}", headers=s2)
    assert resp.status_code == 404
