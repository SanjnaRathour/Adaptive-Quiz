from fastapi.testclient import TestClient

from app.core.config import settings

API = settings.API_V1_PREFIX


def _register(
    client: TestClient,
    *,
    email: str = "alice@example.com",
    password: str = "supersecret",
    role: str = "STUDENT",
    full_name: str = "Alice",
) -> dict:
    return client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": role},
    ).json()


def _login(
    client: TestClient, *, email: str = "alice@example.com", password: str = "supersecret"
) -> dict:
    return client.post(
        f"{API}/auth/login", json={"email": email, "password": password}
    ).json()


def test_register_creates_user(client: TestClient) -> None:
    resp = client.post(
        f"{API}/auth/register",
        json={
            "email": "alice@example.com",
            "password": "supersecret",
            "full_name": "Alice",
            "role": "STUDENT",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "STUDENT"
    assert body["is_active"] is True
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_email_rejected(client: TestClient) -> None:
    _register(client)
    resp = client.post(
        f"{API}/auth/register",
        json={
            "email": "alice@example.com",
            "password": "anotherpass",
            "full_name": "Other",
            "role": "TEACHER",
        },
    )
    assert resp.status_code == 409


def test_register_rejects_weak_password(client: TestClient) -> None:
    resp = client.post(
        f"{API}/auth/register",
        json={"email": "x@example.com", "password": "short", "full_name": "X", "role": "STUDENT"},
    )
    assert resp.status_code == 422


def test_login_with_valid_credentials_returns_tokens(client: TestClient) -> None:
    _register(client)
    resp = client.post(
        f"{API}/auth/login", json={"email": "alice@example.com", "password": "supersecret"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


def test_login_with_wrong_password_rejected(client: TestClient) -> None:
    _register(client)
    resp = client.post(
        f"{API}/auth/login", json={"email": "alice@example.com", "password": "wrong-pass"}
    )
    assert resp.status_code == 401


def test_login_unknown_email_rejected(client: TestClient) -> None:
    resp = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert resp.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    _register(client)
    tokens = _login(client)
    resp = client.get(
        f"{API}/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


def test_me_requires_auth(client: TestClient) -> None:
    resp = client.get(f"{API}/auth/me")
    assert resp.status_code == 401


def test_me_rejects_garbage_token(client: TestClient) -> None:
    resp = client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_refresh_token_rotates_access_token(client: TestClient) -> None:
    _register(client)
    tokens = _login(client)
    resp = client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["access_token"]


def test_refresh_rejects_access_token(client: TestClient) -> None:
    """Sending an access token to /refresh must be rejected (wrong type claim)."""
    _register(client)
    tokens = _login(client)
    resp = client.post(
        f"{API}/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert resp.status_code == 401


def test_email_is_lowercased(client: TestClient) -> None:
    client.post(
        f"{API}/auth/register",
        json={
            "email": "Alice@Example.COM",
            "password": "supersecret",
            "full_name": "Alice",
            "role": "STUDENT",
        },
    )
    # Login with different casing should still work because we lowercase on store + lookup.
    resp = client.post(
        f"{API}/auth/login",
        json={"email": "ALICE@example.com", "password": "supersecret"},
    )
    assert resp.status_code == 200
