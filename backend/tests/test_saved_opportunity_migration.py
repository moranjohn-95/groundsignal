from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from backend.alembic.versions import e4c8a6f19b32_add_saved_opportunities as migration


def test_saved_opportunities_revision_is_single_head():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [migration.revision]
    assert migration.down_revision == "d81f8c0a2b46"


def test_postgresql_upgrade_sql_is_additive():
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    original_op = migration.op
    try:
        migration.op = Operations(context)
        migration.upgrade()
    finally:
        migration.op = original_op
    sql = output.getvalue()
    assert "CREATE TABLE saved_opportunities" in sql
    assert "REFERENCES users (id) ON DELETE CASCADE" in sql
    assert "REFERENCES planning_applications (id) ON DELETE RESTRICT" in sql
    assert "CONSTRAINT uq_saved_opportunities_user_planning UNIQUE (user_id, planning_application_id)" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "CREATE INDEX ix_saved_opportunities_planning_application_id" in sql
    assert "ALTER TABLE users" not in sql
    assert "ALTER TABLE planning_applications" not in sql
    assert "DROP " not in sql
