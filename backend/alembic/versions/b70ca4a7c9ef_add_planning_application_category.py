"""add planning application category

Revision ID: b70ca4a7c9ef
Revises: f38e3c079b2d
Create Date: 2026-08-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b70ca4a7c9ef"
down_revision: Union[str, Sequence[str], None] = "f38e3c079b2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "planning_applications"
CATEGORY_CHECK_NAME = "ck_planning_applications_category"
CATEGORY_INDEX_NAME = "ix_planning_applications_category"
CATEGORY_CHECK_SQL = (
    "category IS NULL OR category IN ("
    "'residential', 'commercial', 'industrial', 'energy', "
    "'infrastructure', 'mixed_use', 'other'"
    ")"
)


def upgrade() -> None:
    """Add nullable, constrained and indexed planning categories."""
    op.add_column(
        TABLE_NAME,
        sa.Column("category", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        CATEGORY_CHECK_NAME,
        TABLE_NAME,
        CATEGORY_CHECK_SQL,
    )
    op.create_index(
        CATEGORY_INDEX_NAME,
        TABLE_NAME,
        ["category"],
        unique=False,
        postgresql_using="btree",
    )


def downgrade() -> None:
    """Remove planning category storage."""
    op.drop_index(CATEGORY_INDEX_NAME, table_name=TABLE_NAME)
    op.drop_constraint(
        CATEGORY_CHECK_NAME,
        TABLE_NAME,
        type_="check",
    )
    op.drop_column(TABLE_NAME, "category")
