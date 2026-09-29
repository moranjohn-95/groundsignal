from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.alembic.versions import d81f8c0a2b46_add_user_sessions as migration
from backend.app.models import Base, User, UserSession


TOKEN = "sample-random-session-token-used-only-in-tests"
TOKEN_HASH = sha256(TOKEN.encode()).hexdigest()
PASSWORD_HASH = "synthetic-password-hash"


@pytest.fixture(params=["model", "migration"])
def session_database(request, monkeypatch):
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    User.__table__.create(engine)
    if request.param == "model":
        UserSession.__table__.create(engine)
    else:
        with engine.begin() as connection:
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
    with engine.begin() as connection:
        user_id = connection.execute(
            insert(User.__table__).values(email="test@example.com", password_hash=PASSWORD_HASH)
        ).inserted_primary_key[0]
    yield engine, user_id
    engine.dispose()


def session_values(user_id, **overrides):
    values = {
        "user_id": user_id,
        "token_hash": TOKEN_HASH,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
    }
    values.update(overrides)
    return values


def test_session_model_has_only_hashed_token_and_tz_timestamps():
    table = Base.metadata.tables["user_sessions"]
    assert table is UserSession.__table__
    assert set(table.c) == {
        table.c.id, table.c.user_id, table.c.token_hash, table.c.created_at,
        table.c.expires_at, table.c.revoked_at,
    }
    assert all(table.c[name].type.timezone for name in ("created_at", "expires_at", "revoked_at"))
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "CASCADE"


def test_session_persists_digest_defaults_and_revocation(session_database):
    engine, user_id = session_database
    with engine.begin() as connection:
        session_id = connection.execute(
            insert(UserSession.__table__).values(**session_values(user_id))
        ).inserted_primary_key[0]
        row = connection.execute(
            select(UserSession.__table__).where(UserSession.id == session_id)
        ).one()
        assert row.token_hash == TOKEN_HASH
        assert TOKEN not in row.token_hash
        assert row.created_at is not None
        assert row.revoked_at is None
        revoked_at = datetime.now(timezone.utc)
        connection.execute(
            update(UserSession.__table__)
            .where(UserSession.id == session_id)
            .values(revoked_at=revoked_at)
        )
        assert connection.execute(
            select(UserSession.revoked_at).where(UserSession.id == session_id)
        ).scalar_one() is not None


def test_token_hash_must_be_unique_across_users(session_database):
    engine, user_id = session_database
    with engine.begin() as connection:
        other_id = connection.execute(
            insert(User.__table__).values(email="other@example.com", password_hash=PASSWORD_HASH)
        ).inserted_primary_key[0]
        connection.execute(insert(UserSession.__table__).values(**session_values(user_id)))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                insert(UserSession.__table__).values(**session_values(other_id))
            )


@pytest.mark.parametrize("field", ["user_id", "token_hash", "expires_at"])
@pytest.mark.parametrize("missing", [True, False])
def test_required_fields_cannot_be_missing_or_null(session_database, field, missing):
    engine, user_id = session_database
    values = session_values(user_id)
    if missing:
        del values[field]
    else:
        values[field] = None
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(UserSession.__table__).values(**values))


def test_short_hash_and_elapsed_expiry_are_rejected(session_database):
    engine, user_id = session_database
    for overrides in (
        {"token_hash": "raw-token"},
        {"expires_at": datetime.now(timezone.utc) - timedelta(days=1)},
    ):
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    insert(UserSession.__table__).values(**session_values(user_id, **overrides))
                )


def test_user_relationship_and_foreign_key_enforced(session_database):
    engine, user_id = session_database
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                insert(UserSession.__table__).values(**session_values(user_id + 999))
            )
    with Session(engine) as session:
        user = session.get(User, user_id)
        login_session = UserSession(**session_values(user_id))
        user.sessions.append(login_session)
        session.commit()
        assert login_session.user.id == user_id
        assert user.sessions == [login_session]
        session.delete(user)
        session.commit()
        assert session.get(UserSession, login_session.id) is None
