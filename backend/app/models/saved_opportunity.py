from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class SavedOpportunity(Base):
    __tablename__ = "saved_opportunities"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "planning_application_id", name="uq_saved_opportunities_user_planning"
        ),
        Index("ix_saved_opportunities_planning_application_id", "planning_application_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    planning_application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planning_applications.id", ondelete="RESTRICT"), nullable=False
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="saved_opportunities")
    planning_application: Mapped["PlanningApplication"] = relationship(
        back_populates="saved_opportunities"
    )
