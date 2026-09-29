from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from backend.alembic.versions import c24a7e91d603_add_users as migration


def test_users_revision_is_the_single_head():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [migration.revision]
    assert migration.down_revision == "b70ca4a7c9ef"


def test_postgresql_upgrade_sql_is_additive(monkeypatch):
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE users" in sql
    assert "CREATE UNIQUE INDEX uq_users_email_normalized ON users (lower(trim(email)))" in sql
    assert "TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL" in sql
    assert "BOOLEAN DEFAULT true NOT NULL" in sql
    assert "planning_applications" not in sql
    assert "DROP " not in sql
    assert "ALTER " not in sql


def test_migration_preserves_existing_table_in_disposable_sqlite(monkeypatch):
    """A sentinel-table check only; real PostGIS migration verification is separate."""
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE planning_applications (id INTEGER PRIMARY KEY, description TEXT)"))
            connection.execute(text("INSERT INTO planning_applications VALUES (42, 'Existing planning record')"))
            before = connection.execute(text("SELECT * FROM planning_applications")).all()
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            assert "users" in inspect(connection).get_table_names()
            assert connection.execute(text("SELECT * FROM planning_applications")).all() == before
            # Downgrade only this ephemeral in-memory database, never development data.
            migration.downgrade()
            assert "users" not in inspect(connection).get_table_names()
            assert connection.execute(text("SELECT * FROM planning_applications")).all() == before
    finally:
        engine.dispose()
