"""Add customer saved opportunities without changing planning records.

Revision ID: e4c8a6f19b32
Revises: d81f8c0a2b46
"""

from alembic import op
import sqlalchemy as sa


revision: str = "e4c8a6f19b32"
down_revision: str = "d81f8c0a2b46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_opportunities",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "planning_application_id", sa.Integer(),
            sa.ForeignKey("planning_applications.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "saved_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "planning_application_id", name="uq_saved_opportunities_user_planning"
        ),
    )
    op.create_index(
        "ix_saved_opportunities_planning_application_id",
        "saved_opportunities", ["planning_application_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_saved_opportunities_planning_application_id", table_name="saved_opportunities"
    )
    op.drop_table("saved_opportunities")
