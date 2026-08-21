import re
from unittest.mock import Mock

from sqlalchemy import String

from backend.alembic.versions import (
    b70ca4a7c9ef_add_planning_application_category as migration,
)
from backend.app.services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
)


def test_category_migration_revisions() -> None:
    assert migration.revision == "b70ca4a7c9ef"
    assert migration.down_revision == "f38e3c079b2d"


def test_category_migration_check_uses_classifier_vocabulary() -> None:
    assert set(re.findall(r"'([^']+)'", migration.CATEGORY_CHECK_SQL)) == set(
        PLANNING_APPLICATION_CATEGORIES
    )


def test_category_migration_upgrade(monkeypatch) -> None:
    operations = Mock()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    table_name, column = operations.add_column.call_args.args
    assert table_name == "planning_applications"
    assert column.name == "category"
    assert isinstance(column.type, String)
    assert column.type.length == 32
    assert column.nullable is True
    assert column.server_default is None

    operations.create_check_constraint.assert_called_once_with(
        "ck_planning_applications_category",
        "planning_applications",
        migration.CATEGORY_CHECK_SQL,
    )
    operations.create_index.assert_called_once_with(
        "ix_planning_applications_category",
        "planning_applications",
        ["category"],
        unique=False,
        postgresql_using="btree",
    )
    assert [call[0] for call in operations.method_calls] == [
        "add_column",
        "create_check_constraint",
        "create_index",
    ]


def test_category_migration_downgrade(monkeypatch) -> None:
    operations = Mock()
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    operations.drop_index.assert_called_once_with(
        "ix_planning_applications_category",
        table_name="planning_applications",
    )
    operations.drop_constraint.assert_called_once_with(
        "ck_planning_applications_category",
        "planning_applications",
        type_="check",
    )
    operations.drop_column.assert_called_once_with(
        "planning_applications",
        "category",
    )
    assert [call[0] for call in operations.method_calls] == [
        "drop_index",
        "drop_constraint",
        "drop_column",
    ]
