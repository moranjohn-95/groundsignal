"""Add customer accounts without changing planning data.

Revision ID: c24a7e91d603
Revises: b70ca4a7c9ef
"""

from alembic import op
import sqlalchemy as sa


revision: str = "c24a7e91d603"
down_revision: str = "b70ca4a7c9ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.CheckConstraint("length(trim(email)) > 0", name="ck_users_email_not_blank"),
        sa.CheckConstraint(
            "length(trim(password_hash)) > 0", name="ck_users_password_hash_not_blank"
        ),
    )
    op.create_index(
        "uq_users_email_normalized", "users",
        [sa.text("lower(trim(email))")], unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_normalized", table_name="users")
    op.drop_table("users")
