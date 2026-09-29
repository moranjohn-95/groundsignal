import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.alembic.versions import c24a7e91d603_add_users as migration
from backend.app.models import Base, User
from backend.app.models.user import normalize_email


# Synthetic encoded hash for persistence tests, not a usable account credential.
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdHNhbHQ$Zml4dHVyZWhhc2g"


@pytest.fixture(params=["model", "migration"])
def user_engine(request, monkeypatch):
    """Exercise both definitions in memory; this does not replace PostgreSQL tests."""
    engine = create_engine("sqlite://")
    if request.param == "model":
        User.__table__.create(engine)
    else:
        with engine.begin() as connection:
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
    yield engine
    engine.dispose()


def test_user_registered_without_plaintext_password_column():
    assert Base.metadata.tables["users"] is User.__table__
    assert set(User.__table__.c.keys()) == {
        "id", "email", "password_hash", "is_active", "created_at"
    }
    assert User.__table__.c.created_at.type.timezone is True


def test_email_normalization_on_creation_and_assignment():
    user = User(email="  Alice+Work@Example.COM  ", password_hash=PASSWORD_HASH)
    assert user.email == "alice+work@example.com"
    user.email = " OTHER@Example.COM "
    assert user.email == "other@example.com"
    assert normalize_email(user.email) == user.email


@pytest.mark.parametrize("duplicate", ["alice@example.com", "ALICE@EXAMPLE.COM", " Alice@Example.com "])
def test_database_rejects_duplicate_email_without_orm_validation(user_engine, duplicate):
    with user_engine.begin() as connection:
        connection.execute(insert(User.__table__).values(
            email="Alice@Example.com", password_hash=PASSWORD_HASH
        ))
    with pytest.raises(IntegrityError):
        with user_engine.begin() as connection:
            connection.execute(insert(User.__table__).values(
                email=duplicate, password_hash=PASSWORD_HASH
            ))


@pytest.mark.parametrize("field", ["email", "password_hash"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_database_rejects_missing_or_blank_required_values(user_engine, field, value):
    values = {"email": "alice@example.com", "password_hash": PASSWORD_HASH, field: value}
    with pytest.raises(IntegrityError):
        with user_engine.begin() as connection:
            connection.execute(insert(User.__table__).values(**values))


@pytest.mark.parametrize("field", ["email", "password_hash"])
def test_database_rejects_omitted_required_fields(user_engine, field):
    values = {"email": "alice@example.com", "password_hash": PASSWORD_HASH}
    del values[field]
    with pytest.raises(IntegrityError):
        with user_engine.begin() as connection:
            connection.execute(insert(User.__table__).values(**values))


@pytest.mark.parametrize("field", ["is_active", "created_at"])
def test_explicit_null_cannot_bypass_defaults(user_engine, field):
    with pytest.raises(IntegrityError):
        with user_engine.begin() as connection:
            connection.execute(insert(User.__table__).values(
                email="alice@example.com", password_hash=PASSWORD_HASH, **{field: None}
            ))


def test_database_defaults_and_explicit_inactive_status(user_engine):
    with user_engine.begin() as connection:
        connection.execute(insert(User.__table__).values(
            email="alice@example.com", password_hash=PASSWORD_HASH
        ))
        connection.execute(insert(User.__table__).values(
            email="bob@example.com", password_hash=PASSWORD_HASH, is_active=False
        ))
    with Session(user_engine) as session:
        active, inactive = session.scalars(select(User).order_by(User.id)).all()
        assert active.id > 0
        assert inactive.id != active.id
        assert active.is_active is True
        assert inactive.is_active is False
        assert active.created_at is not None
        assert inactive.created_at is not None
        assert active.password_hash == PASSWORD_HASH


def test_email_update_cannot_collide_with_another_user(user_engine):
    with Session(user_engine) as session:
        first = User(email="alice@example.com", password_hash=PASSWORD_HASH)
        second = User(email="bob@example.com", password_hash=PASSWORD_HASH)
        session.add_all([first, second])
        session.commit()
        second.email = " ALICE@EXAMPLE.COM "
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert second.email == "bob@example.com"
