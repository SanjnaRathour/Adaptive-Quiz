"""Scenarios for in-flight attempts when teacher edits the quiz mid-attempt.

The contract:
  - Attempt's question pool is frozen at start_attempt time.
  - Questions ADDED to the quiz after attempt start do NOT appear in that
    attempt.
  - Questions DELETED (soft) after attempt start are filtered out, but if
    the student already answered them the answer is preserved in scoring
    and results.
  - Soft delete never removes the row — historical results still resolve.
"""
from fastapi.testclient import TestClient

from app.tests.helpers import (
    API,
    auth_headers,
    make_mcq_payload,
    student_token,
    teacher_token,
)


def _make_quiz_with_questions(
    client: TestClient, t_headers: dict, n: int
) -> tuple[dict, list[dict]]:
    quiz = client.post(
        f"{API}/quizzes",
        json={"title": "Snap", "subject": "Test", "is_adaptive": False},
        headers=t_headers,
    ).json()
    questions = []
    for i in range(n):
        q = client.post(
            f"{API}/quizzes/{quiz['id']}/questions",
            json=make_mcq_payload(
                text=f"Q{i}", correct=str(i), others=("X", "Y", "Z")
            ),
            headers=t_headers,
        ).json()
        questions.append(q)
    client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t_headers)
    return quiz, questions


def _correct_option(q: dict) -> str:
    return next(o for o in q["options"] if o["is_correct"])["id"]


def test_question_added_after_start_not_in_active_attempt(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, qs = _make_quiz_with_questions(client, t, n=2)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()

    # Teacher adds a third question AFTER the student started the attempt.
    extra = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(text="late-add", correct="A", others=("B",)),
        headers=t,
    ).json()
    assert extra["id"]

    # Student answers all questions they were given.
    seen_ids: list[str] = []
    for _ in range(5):  # safety bound
        nq = client.get(
            f"{API}/attempts/{attempt['id']}/next-question", headers=s
        ).json()
        if nq["question"] is None:
            break
        seen_ids.append(nq["question"]["id"])
        # answer correctly with the snapshot question
        full = next(q for q in qs if q["id"] == nq["question"]["id"])
        client.post(
            f"{API}/attempts/{attempt['id']}/answers",
            json={
                "question_id": nq["question"]["id"],
                "selected_option_id": _correct_option(full),
            },
            headers=s,
        )

    # The late-added question must NEVER appear in this attempt.
    assert extra["id"] not in seen_ids
    assert len(seen_ids) == 2  # only the original 2

    completed = client.post(
        f"{API}/attempts/{attempt['id']}/complete", headers=s
    ).json()
    assert completed["score"] == 100.0  # 2/2 correct, 100%


def test_late_add_appears_in_NEW_attempt(client: TestClient) -> None:
    """A second student starting after the addition sees the new question."""
    t = auth_headers(teacher_token(client))
    s1 = auth_headers(student_token(client, email="s1@example.com"))
    s2 = auth_headers(student_token(client, email="s2@example.com"))
    quiz, _ = _make_quiz_with_questions(client, t, n=2)

    a1 = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s1).json()
    extra = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(text="late-add", correct="A", others=("B",)),
        headers=t,
    ).json()
    a2 = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s2).json()
    assert a1["id"] != a2["id"]

    # s2's pool should include the late-add.
    seen: set[str] = set()
    for _ in range(5):
        nq = client.get(
            f"{API}/attempts/{a2['id']}/next-question", headers=s2
        ).json()
        if nq["question"] is None:
            break
        seen.add(nq["question"]["id"])
        client.post(
            f"{API}/attempts/{a2['id']}/answers",
            json={
                "question_id": nq["question"]["id"],
                "selected_option_id": nq["question"]["options"][0]["id"],
            },
            headers=s2,
        )
    assert extra["id"] in seen


def test_soft_deleted_question_skipped_in_active_attempt(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, qs = _make_quiz_with_questions(client, t, n=3)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()

    # Soft-delete the second question BEFORE student answers anything.
    resp = client.delete(
        f"{API}/quizzes/questions/{qs[1]['id']}", headers=t
    )
    assert resp.status_code == 204

    seen: list[str] = []
    for _ in range(5):
        nq = client.get(
            f"{API}/attempts/{attempt['id']}/next-question", headers=s
        ).json()
        if nq["question"] is None:
            break
        seen.append(nq["question"]["id"])
        full = next(q for q in qs if q["id"] == nq["question"]["id"])
        client.post(
            f"{API}/attempts/{attempt['id']}/answers",
            json={
                "question_id": nq["question"]["id"],
                "selected_option_id": _correct_option(full),
            },
            headers=s,
        )

    # The deleted question never gets shown.
    assert qs[1]["id"] not in seen
    # The other two are.
    assert qs[0]["id"] in seen
    assert qs[2]["id"] in seen


def test_already_answered_question_preserved_when_deleted(client: TestClient) -> None:
    """Student answers Q2 correctly, then teacher soft-deletes Q2.
    The answer must still count toward the score and show in results.
    """
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, qs = _make_quiz_with_questions(client, t, n=2)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()

    # Answer both correctly.
    for q in qs:
        client.post(
            f"{API}/attempts/{attempt['id']}/answers",
            json={
                "question_id": q["id"],
                "selected_option_id": _correct_option(q),
            },
            headers=s,
        )

    # Now teacher deletes one of the answered questions.
    client.delete(f"{API}/quizzes/questions/{qs[1]['id']}", headers=t)

    completed = client.post(
        f"{API}/attempts/{attempt['id']}/complete", headers=s
    ).json()
    assert completed["score"] == 100.0  # both answers preserved

    results = client.get(
        f"{API}/attempts/{attempt['id']}/results", headers=s
    ).json()
    # Both questions still show in results — the deleted one too.
    qids = {d["question_id"] for d in results["details"]}
    assert qs[0]["id"] in qids
    assert qs[1]["id"] in qids
    assert results["correct_count"] == 2


def test_answer_rejected_for_question_not_in_snapshot(client: TestClient) -> None:
    """Trying to submit an answer for a question added AFTER attempt start
    must be rejected — that question isn't in this attempt's pool."""
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, _ = _make_quiz_with_questions(client, t, n=1)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()

    extra = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(text="extra", correct="A", others=("B",)),
        headers=t,
    ).json()

    resp = client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={
            "question_id": extra["id"],
            "selected_option_id": _correct_option(extra),
        },
        headers=s,
    )
    assert resp.status_code == 400


def test_answer_rejected_for_soft_deleted_question(client: TestClient) -> None:
    """If the teacher deletes Q1 while the student is mid-attempt, attempting
    to submit for Q1 must fail."""
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, qs = _make_quiz_with_questions(client, t, n=2)

    attempt = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    client.delete(f"{API}/quizzes/questions/{qs[0]['id']}", headers=t)

    resp = client.post(
        f"{API}/attempts/{attempt['id']}/answers",
        json={
            "question_id": qs[0]["id"],
            "selected_option_id": _correct_option(qs[0]),
        },
        headers=s,
    )
    assert resp.status_code == 400


def test_soft_delete_hides_from_question_listing(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=t
    ).json()
    a = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(text="alive"),
        headers=t,
    ).json()
    b = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(text="doomed"),
        headers=t,
    ).json()
    client.delete(f"{API}/quizzes/questions/{b['id']}", headers=t)

    listing = client.get(
        f"{API}/quizzes/{quiz['id']}/questions", headers=t
    ).json()
    ids = {q["id"] for q in listing}
    assert a["id"] in ids
    assert b["id"] not in ids


def test_question_count_excludes_soft_deleted(client: TestClient) -> None:
    t = auth_headers(teacher_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=t
    ).json()
    for i in range(3):
        client.post(
            f"{API}/quizzes/{quiz['id']}/questions",
            json=make_mcq_payload(text=f"Q{i}"),
            headers=t,
        )
    listing = client.get(f"{API}/quizzes/{quiz['id']}", headers=t).json()
    assert listing["question_count"] == 3

    questions = client.get(
        f"{API}/quizzes/{quiz['id']}/questions", headers=t
    ).json()
    client.delete(f"{API}/quizzes/questions/{questions[0]['id']}", headers=t)

    listing = client.get(f"{API}/quizzes/{quiz['id']}", headers=t).json()
    assert listing["question_count"] == 2


def test_publish_with_only_deleted_questions_is_blocked(client: TestClient) -> None:
    """If every question on a quiz is soft-deleted, count is 0 → publish 400."""
    t = auth_headers(teacher_token(client))
    quiz = client.post(
        f"{API}/quizzes", json={"title": "X", "subject": "Y"}, headers=t
    ).json()
    q = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(),
        headers=t,
    ).json()
    client.delete(f"{API}/quizzes/questions/{q['id']}", headers=t)

    resp = client.post(f"{API}/quizzes/{quiz['id']}/publish", headers=t)
    assert resp.status_code == 400


def test_resuming_attempt_returns_existing_with_same_snapshot(client: TestClient) -> None:
    """Calling start_attempt twice while in-progress returns the same attempt.
    A question added between the two calls must NOT enter the snapshot."""
    t = auth_headers(teacher_token(client))
    s = auth_headers(student_token(client))
    quiz, _ = _make_quiz_with_questions(client, t, n=1)

    a1 = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    extra = client.post(
        f"{API}/quizzes/{quiz['id']}/questions",
        json=make_mcq_payload(text="late"),
        headers=t,
    ).json()
    a2 = client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=s).json()
    assert a1["id"] == a2["id"]

    # Walk through next-question; the late-add must not appear.
    seen: list[str] = []
    for _ in range(3):
        nq = client.get(
            f"{API}/attempts/{a1['id']}/next-question", headers=s
        ).json()
        if nq["question"] is None:
            break
        seen.append(nq["question"]["id"])
        client.post(
            f"{API}/attempts/{a1['id']}/answers",
            json={
                "question_id": nq["question"]["id"],
                "selected_option_id": nq["question"]["options"][0]["id"],
            },
            headers=s,
        )
    assert extra["id"] not in seen
