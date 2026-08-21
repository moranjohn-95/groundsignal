import re

from sqlalchemy import CheckConstraint, String, UniqueConstraint

from backend.app.models import PlanningApplication
from backend.app.services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
)


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


def test_category_is_nullable_string_column() -> None:
    category = PlanningApplication.__table__.c.category

    assert isinstance(category.type, String)
    assert category.type.length == 32
    assert category.nullable is True
    assert category.server_default is None


def test_category_check_constraint_uses_classifier_vocabulary() -> None:
    constraint = next(
        constraint
        for constraint in PlanningApplication.__table__.constraints
        if constraint.name == "ck_planning_applications_category"
    )

    assert isinstance(constraint, CheckConstraint)
    assert set(re.findall(r"'([^']+)'", str(constraint.sqltext))) == set(
        PLANNING_APPLICATION_CATEGORIES
    )
    assert "category IS NULL OR category IN" in str(constraint.sqltext)


def test_category_has_non_unique_btree_index() -> None:
    index = next(
        index
        for index in PlanningApplication.__table__.indexes
        if index.name == "ix_planning_applications_category"
    )

    assert [column.name for column in index.columns] == ["category"]
    assert index.unique is False
    assert index.dialect_options["postgresql"]["using"] == "btree"
