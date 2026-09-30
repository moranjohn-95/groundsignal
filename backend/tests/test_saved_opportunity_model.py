import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.alembic.versions import e4c8a6f19b32_add_saved_opportunities as migration
from backend.app.models import Base, PlanningApplication, SavedOpportunity, User


@pytest.fixture(params=["model", "migration"])
def saved_database(request, monkeypatch):
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    # SQLite cannot create the real PostGIS geography column. The disposable
    # PostgreSQL migration check exercises the complete planning table.
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE planning_applications (id INTEGER PRIMARY KEY)"))
    User.__table__.create(engine)
    if request.param == "model":
        SavedOpportunity.__table__.create(engine)
    else:
        with engine.begin() as connection:
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()

    with engine.begin() as connection:
        user_id = connection.execute(
            insert(User.__table__).values(
                email="customer@example.com", password_hash="synthetic-password-hash"
            )
        ).inserted_primary_key[0]
        connection.execute(text("INSERT INTO planning_applications (id) VALUES (42), (43)"))
    yield engine, user_id
    engine.dispose()


def test_registered_relationships_and_delete_policies():
    table = Base.metadata.tables["saved_opportunities"]
    assert table is SavedOpportunity.__table__
    assert set(table.c.keys()) == {"id", "user_id", "planning_application_id", "saved_at"}
    assert table.c.saved_at.type.timezone is True
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "CASCADE"
    assert next(iter(table.c.planning_application_id.foreign_keys)).ondelete == "RESTRICT"

    user = User(email="customer@example.com", password_hash="synthetic-password-hash")
    planning = PlanningApplication(
        source_object_id=42, planning_authority="Sample Council", application_number="24/42"
    )
    saved = SavedOpportunity(user=user, planning_application=planning)
    assert saved.user is user
    assert saved.planning_application is planning
    assert saved in user.saved_opportunities
    assert saved in planning.saved_opportunities


def test_save_defaults_and_user_relationship(saved_database):
    engine, user_id = saved_database
    with engine.begin() as connection:
        save_id = connection.execute(
            insert(SavedOpportunity.__table__).values(
                user_id=user_id, planning_application_id=42
            )
        ).inserted_primary_key[0]
    with Session(engine) as session:
        user = session.get(User, user_id)
        saved = session.get(SavedOpportunity, save_id)
        assert saved.saved_at is not None
        assert saved.user is user
        assert user.saved_opportunities == [saved]
        assert saved.planning_application_id == 42


def test_duplicate_save_rejected_but_other_pairs_allowed(saved_database):
    engine, user_id = saved_database
    with engine.begin() as connection:
        other_user_id = connection.execute(
            insert(User.__table__).values(
                email="other@example.com", password_hash="synthetic-password-hash"
            )
        ).inserted_primary_key[0]
        connection.execute(insert(SavedOpportunity.__table__).values(
            user_id=user_id, planning_application_id=42
        ))
        connection.execute(insert(SavedOpportunity.__table__).values(
            user_id=user_id, planning_application_id=43
        ))
        connection.execute(insert(SavedOpportunity.__table__).values(
            user_id=other_user_id, planning_application_id=42
        ))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(SavedOpportunity.__table__).values(
                user_id=user_id, planning_application_id=42
            ))


@pytest.mark.parametrize("field", ["user_id", "planning_application_id"])
def test_required_foreign_keys_reject_missing_null_and_unknown(saved_database, field):
    engine, user_id = saved_database
    for value in ("missing", None, 999):
        values = {"user_id": user_id, "planning_application_id": 42}
        if value == "missing":
            del values[field]
        else:
            values[field] = value
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(insert(SavedOpportunity.__table__).values(**values))


def test_planning_delete_is_restricted_until_save_removed(saved_database):
    engine, user_id = saved_database
    with engine.begin() as connection:
        connection.execute(insert(SavedOpportunity.__table__).values(
            user_id=user_id, planning_application_id=42
        ))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM planning_applications WHERE id = 42"))
    with engine.begin() as connection:
        assert connection.execute(text("SELECT id FROM planning_applications WHERE id = 42")).scalar_one() == 42
        assert connection.execute(select(SavedOpportunity.id)).scalar_one() > 0
        connection.execute(text("DELETE FROM saved_opportunities WHERE planning_application_id = 42"))
        connection.execute(text("DELETE FROM planning_applications WHERE id = 42"))
        assert connection.execute(text("SELECT count(*) FROM planning_applications WHERE id = 42")).scalar_one() == 0


def test_deleting_user_removes_only_their_saves(saved_database):
    engine, user_id = saved_database
    with engine.begin() as connection:
        other_user_id = connection.execute(
            insert(User.__table__).values(
                email="other@example.com", password_hash="synthetic-password-hash"
            )
        ).inserted_primary_key[0]
        connection.execute(insert(SavedOpportunity.__table__).values(
            user_id=user_id, planning_application_id=42
        ))
        connection.execute(insert(SavedOpportunity.__table__).values(
            user_id=other_user_id, planning_application_id=42
        ))
        connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        remaining = connection.execute(select(SavedOpportunity.user_id)).all()
        assert remaining == [(other_user_id,)]
        assert connection.execute(text("SELECT id FROM planning_applications WHERE id = 42")).scalar_one() == 42
