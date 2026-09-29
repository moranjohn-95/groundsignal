from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from backend.alembic.versions import d81f8c0a2b46_add_user_sessions as migration
from backend.app.models import User


def test_sessions_revision_follows_users_and_is_single_head():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [migration.revision]
    assert migration.down_revision == "c24a7e91d603"


def test_postgresql_upgrade_sql_is_additive(monkeypatch):
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE user_sessions" in sql
    assert "REFERENCES users (id) ON DELETE CASCADE" in sql
    assert "UNIQUE (token_hash)" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "CREATE INDEX ix_user_sessions_user_id" in sql
    assert "ALTER TABLE users" not in sql
    assert "planning_applications" not in sql
    assert "DROP " not in sql


def test_migration_preserves_existing_users_in_disposable_sqlite(monkeypatch):
    engine = create_engine("sqlite://")
    try:
        User.__table__.create(engine)
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (email, password_hash) VALUES "
                "('sample@example.com', 'synthetic-password-hash')"
            ))
            before = connection.execute(text("SELECT id, email, password_hash FROM users")).all()
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            assert "user_sessions" in inspect(connection).get_table_names()
            assert connection.execute(text("SELECT id, email, password_hash FROM users")).all() == before
    finally:
        engine.dispose()
