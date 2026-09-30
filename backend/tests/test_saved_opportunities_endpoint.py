from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.dependencies import get_db
from backend.app.main import app
from backend.app.models import SavedOpportunity, User, UserSession
from backend.app.services import authentication as auth


ORIGIN = "http://localhost:5173"
PASSWORD = "a-long-test-password-123"
SAVES_URL = "/api/v1/saved-opportunities"


@pytest.fixture
def saved_clients(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", ORIGIN)
    monkeypatch.setattr(
        auth, "password_hasher", PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
    )
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

    # The endpoint reads public planning columns only. The real PostGIS model
    # and migration are exercised separately on disposable PostgreSQL.
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE planning_applications (
                id INTEGER PRIMARY KEY, source_object_id INTEGER NOT NULL,
                planning_authority TEXT NOT NULL, application_number TEXT NOT NULL,
                description TEXT, address TEXT, postcode TEXT, application_status TEXT,
                application_type TEXT, decision TEXT, received_date DATE,
                decision_date DATE, grant_date DATE, number_residential_units INTEGER,
                floor_area FLOAT, application_url TEXT, source_updated_at DATETIME
            )
        """))
        connection.execute(text("""
            INSERT INTO planning_applications (
                id, source_object_id, planning_authority, application_number,
                description, address, application_type, application_status,
                received_date, application_url
            ) VALUES
            (1, 101, 'Sample Council', 'TEST-1', 'New electrical installation',
             'Main Street', 'Permission', 'Pending', '2026-09-29',
             'https://example.test/planning/1'),
            (2, 102, 'Sample Council', 'TEST-2', 'New EV charging hub',
             'Station Road', 'Permission', 'Pending', '2026-09-28',
             'javascript:alert(1)')
        """))
    User.__table__.create(engine)
    UserSession.__table__.create(engine)
    SavedOpportunity.__table__.create(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with (
            TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as alice,
            TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as bob,
        ):
            yield alice, bob, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        for limiter in (
            auth.signup_ip_limiter, auth.signup_email_limiter,
            auth.login_ip_limiter, auth.login_email_limiter,
        ):
            limiter.clear()


def signup(client: TestClient, email: str) -> int:
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()["id"]


def save(client: TestClient, planning_id: int):
    return client.post(SAVES_URL, json={"planning_application_id": planning_id})


def assert_private(response, status_code: int):
    assert response.status_code == status_code
    assert response.headers["cache-control"] == "no-store"


def test_save_is_idempotent_and_returns_card_information(saved_clients):
    alice, _bob, engine = saved_clients
    user_id = signup(alice, "alice@example.test")
    created = save(alice, 1)
    assert_private(created, 201)
    item = created.json()
    assert isinstance(item["id"], int)
    assert item["saved_at"] is not None
    assert item["opportunity"]["id"] == 1
    assert item["opportunity"]["application_number"] == "TEST-1"
    assert item["opportunity"]["planning_authority"] == "Sample Council"
    assert item["opportunity"]["opportunity_score"] >= 0
    assert item["opportunity"]["application_url"] == "https://example.test/planning/1"
    assert "user_id" not in item

    repeated = save(alice, 1)
    assert_private(repeated, 200)
    assert repeated.json()["id"] == item["id"]
    assert repeated.json()["saved_at"] == item["saved_at"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SavedOpportunity)) == 1
        assert session.scalar(select(SavedOpportunity.user_id)) == user_id


def test_nonexistent_opportunity_and_browser_ownership_are_rejected(saved_clients):
    alice, bob, engine = saved_clients
    signup(alice, "alice@example.test")
    bob_id = signup(bob, "bob@example.test")
    assert_private(save(alice, 999), 404)
    assert_private(save(alice, -1), 422)
    spoofed = alice.post(SAVES_URL, json={"planning_application_id": 1, "user_id": bob_id})
    assert_private(spoofed, 422)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SavedOpportunity)) == 0


def test_list_is_isolated_and_cross_customer_removal_returns_404(saved_clients):
    alice, bob, engine = saved_clients
    signup(alice, "alice@example.test")
    signup(bob, "bob@example.test")
    alice_first = save(alice, 1).json()["id"]
    alice_second = save(alice, 2).json()["id"]
    bob_first = save(bob, 1).json()["id"]

    alice_list = alice.get(SAVES_URL)
    assert_private(alice_list, 200)
    assert alice_list.json()["total"] == 2
    assert {item["id"] for item in alice_list.json()["items"]} == {alice_first, alice_second}
    assert all(item["opportunity"]["id"] in {1, 2} for item in alice_list.json()["items"])
    assert next(item for item in alice_list.json()["items"] if item["id"] == alice_second)["opportunity"]["application_url"] is None
    page = alice.get(SAVES_URL, params={"limit": 1, "offset": 1})
    assert_private(page, 200)
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert_private(alice.get(SAVES_URL, params={"limit": 101}), 422)

    bob_list = bob.get(SAVES_URL)
    assert_private(bob_list, 200)
    assert [item["id"] for item in bob_list.json()["items"]] == [bob_first]
    assert_private(bob.delete(f"{SAVES_URL}/{alice_first}"), 404)
    assert_private(alice.delete(f"{SAVES_URL}/{bob_first}"), 404)
    assert_private(alice.get(SAVES_URL), 200)
    assert alice.get(SAVES_URL).json()["total"] == 2

    assert_private(alice.delete(f"{SAVES_URL}/{alice_first}"), 204)
    assert_private(alice.delete(f"{SAVES_URL}/{alice_first}"), 404)
    assert alice.get(SAVES_URL).json()["total"] == 1
    assert bob.get(SAVES_URL).json()["total"] == 1
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SavedOpportunity)) == 2


def test_session_and_origin_guards_cover_every_private_operation(saved_clients):
    alice, _bob, engine = saved_clients
    for response in (
        alice.get(SAVES_URL), save(alice, 1), alice.delete(f"{SAVES_URL}/1")
    ):
        assert_private(response, 401)

    signup(alice, "alice@example.test")
    saved_id = save(alice, 1).json()["id"]
    assert_private(alice.post(SAVES_URL, json={"planning_application_id": 2}, headers={"Origin": "https://evil.example"}), 403)
    assert_private(alice.delete(f"{SAVES_URL}/{saved_id}", headers={"Origin": "https://evil.example"}), 403)
    assert_private(alice.post(SAVES_URL, json={"planning_application_id": 2}, headers={"Sec-Fetch-Site": "cross-site"}), 403)
    assert_private(alice.post(SAVES_URL, content="planning_application_id=2", headers={"Content-Type": "text/plain"}), 415)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SavedOpportunity)) == 1

    with Session(engine) as session:
        session.execute(update(UserSession).values(
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        ))
        session.commit()
    for response in (
        alice.get(SAVES_URL), save(alice, 2), alice.delete(f"{SAVES_URL}/{saved_id}")
    ):
        assert_private(response, 401)

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SavedOpportunity)) == 1


def test_logout_revokes_access_even_if_cookie_is_replayed(saved_clients):
    alice, _bob, engine = saved_clients
    signup(alice, "alice@example.test")
    saved_id = save(alice, 1).json()["id"]
    old_token = alice.cookies.get(auth.SESSION_COOKIE_NAME)
    assert_private(alice.get(SAVES_URL), 200)
    assert alice.post("/api/v1/auth/logout").status_code == 204
    alice.cookies.set(auth.SESSION_COOKIE_NAME, old_token)
    for response in (
        alice.get(SAVES_URL), save(alice, 2), alice.delete(f"{SAVES_URL}/{saved_id}")
    ):
        assert_private(response, 401)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SavedOpportunity)) == 1
