from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.dependencies import get_db
from backend.app.main import app
from backend.app.models import User, UserSession
from backend.app.services import authentication as auth


ORIGIN = "http://localhost:5173"
PASSWORD = "a-long-test-password-123"


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", ORIGIN)
    monkeypatch.setattr(auth, "password_hasher", PasswordHasher(
        time_cost=1, memory_cost=8192, parallelism=1
    ))
    monkeypatch.setattr(auth, "_dummy_password_hash", auth.password_hasher.hash("dummy-password"))
    for limiter in (
        auth.signup_ip_limiter, auth.signup_email_limiter,
        auth.login_ip_limiter, auth.login_email_limiter,
    ):
        limiter.clear()

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    User.__table__.create(engine)
    UserSession.__table__.create(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()
    for limiter in (
        auth.signup_ip_limiter, auth.signup_email_limiter,
        auth.login_ip_limiter, auth.login_email_limiter,
    ):
        limiter.clear()


def signup(client, email=" Alice@Example.COM ", password=PASSWORD):
    return client.post("/api/v1/auth/signup", json={"email": email, "password": password})


def login(client, email="alice@example.com", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_signup_normalizes_email_hashes_password_and_logs_in(auth_client):
    client, engine = auth_client
    response = signup(client)
    assert response.status_code == 201
    assert set(response.json()) == {"id", "email", "is_active", "created_at"}
    assert response.json()["email"] == "alice@example.com"
    assert response.json()["is_active"] is True
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Secure" not in cookie
    assert "Max-Age=604800" in cookie
    token = client.cookies.get(auth.SESSION_COOKIE_NAME)
    assert token is not None
    with Session(engine) as db:
        user = db.scalar(select(User))
        login_session = db.scalar(select(UserSession))
        assert user.email == "alice@example.com"
        assert user.password_hash.startswith("$argon2id$")
        assert user.password_hash != PASSWORD
        assert auth.verify_password(user.password_hash, PASSWORD)
        assert login_session.user_id == user.id
        assert login_session.token_hash == auth.hash_session_token(token)
        assert token != login_session.token_hash
    assert client.get("/api/v1/auth/me").json()["email"] == "alice@example.com"


def test_login_uses_generic_errors_and_rotates_existing_session(auth_client):
    client, engine = auth_client
    assert signup(client).status_code == 201
    old_token = client.cookies.get(auth.SESSION_COOKIE_NAME)
    response = login(client, email="  ALICE@EXAMPLE.COM  ")
    assert response.status_code == 200
    new_token = client.cookies.get(auth.SESSION_COOKIE_NAME)
    assert new_token != old_token
    with Session(engine) as db:
        old = db.scalar(select(UserSession).where(
            UserSession.token_hash == auth.hash_session_token(old_token)
        ))
        assert old.revoked_at is not None
    client.cookies.set(auth.SESSION_COOKIE_NAME, old_token)
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.set(auth.SESSION_COOKIE_NAME, new_token)
    assert client.get("/api/v1/auth/me").status_code == 200
    client.cookies.clear()
    for email, password in (
        ("alice@example.com", "wrong-password"),
        ("missing@example.com", PASSWORD),
    ):
        invalid = login(client, email=email, password=password)
        assert invalid.status_code == 401
        assert invalid.json() == {"detail": "Invalid credentials."}
        assert auth.SESSION_COOKIE_NAME not in invalid.headers.get("set-cookie", "")


def test_duplicate_email_and_invalid_signup_do_not_create_accounts(auth_client):
    client, engine = auth_client
    assert signup(client).status_code == 201
    duplicate = signup(client, email="ALICE@example.com")
    assert duplicate.status_code == 409
    assert signup(client, email="invalid-email").status_code == 422
    invalid_password = signup(client, email="valid@example.com", password="short")
    assert invalid_password.status_code == 422
    assert "short" not in invalid_password.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(UserSession)) == 1


def test_logout_revokes_session_and_replay_fails(auth_client):
    client, engine = auth_client
    assert signup(client).status_code == 201
    token = client.cookies.get(auth.SESSION_COOKIE_NAME)
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").status_code == 401
    with Session(engine) as db:
        assert db.scalar(select(UserSession.revoked_at)) is not None
    client.cookies.set(auth.SESSION_COOKIE_NAME, token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_inactive_and_unknown_sessions_are_denied(auth_client):
    client, engine = auth_client
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.set(auth.SESSION_COOKIE_NAME, "unknown-token")
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    assert signup(client).status_code == 201
    with Session(engine) as db:
        db.execute(update(UserSession).values(
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        ))
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    with Session(engine) as db:
        db.execute(update(UserSession).values(expires_at=datetime.now(timezone.utc) + timedelta(days=1)))
        db.execute(update(User).values(is_active=False))
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    assert login(client).status_code == 401


def test_csrf_and_content_type_guards_all_mutations(auth_client):
    client, engine = auth_client
    payload = {"email": "alice@example.com", "password": PASSWORD}
    assert client.post("/api/v1/auth/signup", json=payload, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/auth/signup", json=payload, headers={"Origin": ""}).status_code == 403
    assert client.post("/api/v1/auth/signup", json=payload, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/v1/auth/signup", content="email=alice", headers={"Content-Type": "text/plain"}).status_code in {415, 422}
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
    assert signup(client).status_code == 201
    assert client.post("/api/v1/auth/login", json=payload, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200


def test_auth_rate_limits_failed_login_and_signup(auth_client):
    client, engine = auth_client
    for _ in range(5):
        assert login(client, email="missing@example.com").status_code == 401
    limited = login(client, email="missing@example.com")
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "900"
    assert signup(client, email="repeat@example.com").status_code == 201
    for _ in range(2):
        assert signup(client, email="repeat@example.com").status_code == 409
    assert signup(client, email="repeat@example.com").status_code == 429
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1


def test_production_cookie_is_secure_and_insecure_production_config_rejected(auth_client, monkeypatch):
    _client, engine = auth_client
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://siteforecaster.com")
    with TestClient(app, base_url="https://siteforecaster.com", headers={
        "Origin": "https://siteforecaster.com"
    }) as client:
        response = signup(client, email="secure@example.com")
        assert response.status_code == 201
        assert "Secure" in response.headers["set-cookie"]
        assert client.get("/api/v1/auth/me").status_code == 200
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with pytest.raises(RuntimeError, match="APP_ENV=development"):
        auth.get_auth_settings()
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://remote.example")
    with pytest.raises(RuntimeError, match="trusted origins"):
        auth.get_auth_settings()
