from sqlalchemy import UniqueConstraint

from backend.app.models import PlanningApplication


def test_source_object_id_remains_unique() -> None:
    table = PlanningApplication.__table__
    source_object_id = table.c.source_object_id

    assert source_object_id.unique is True
    assert any(
        index.unique
        and [column.name for column in index.columns] == ["source_object_id"]
        for index in table.indexes
    )


def test_authority_and_application_number_are_not_unique() -> None:
    table = PlanningApplication.__table__
    composite_columns = {"planning_authority", "application_number"}

    assert not any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == composite_columns
        for constraint in table.constraints
    )


def test_authority_application_number_lookup_index_is_non_unique() -> None:
    table = PlanningApplication.__table__
    index = next(
        index
        for index in table.indexes
        if index.name == "ix_planning_applications_authority_application_number"
    )

    assert [column.name for column in index.columns] == [
        "planning_authority",
        "application_number",
    ]
    assert index.unique is False
