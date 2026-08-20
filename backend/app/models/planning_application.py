from datetime import date, datetime

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import Date, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class PlanningApplication(Base):
    __tablename__ = "planning_applications"
    __table_args__ = (
        Index(
            "ix_planning_applications_authority_application_number",
            "planning_authority",
            "application_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_object_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )
    planning_authority: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    application_number: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    postcode: Mapped[str | None] = mapped_column(String, nullable=True)
    application_status: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )
    application_type: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )
    received_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    decision_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    grant_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    number_residential_units: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    floor_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    application_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[WKBElement | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
