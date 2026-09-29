from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from . import Base


def normalize_email(email: str) -> str:
    """Treat email addresses as case-insensitive; trim surrounding spaces.

    Match the database index's lower(trim(email)) policy. Do not rewrite dots
    or plus tags: provider-specific aliases are outside the account contract.
    Email syntax validation belongs at the future signup boundary.
    """
    return email.strip(" ").lower()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(email)) > 0", name="ck_users_email_not_blank"),
        CheckConstraint(
            "length(trim(password_hash)) > 0", name="ck_users_password_hash_not_blank"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @validates("email")
    def _normalize_email(self, key: str, value: str) -> str:
        return normalize_email(value)


# Protect all write paths, including SQL that bypasses ORM validators.
Index("uq_users_email_normalized", func.lower(func.trim(User.email)), unique=True)
