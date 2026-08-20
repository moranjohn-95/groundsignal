from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, load_only

from ..dependencies import get_db
from ..models import PlanningApplication
from ..schemas import PlanningApplicationListResponse


router = APIRouter(
    prefix="/api/v1/planning-applications",
    tags=["planning-applications"],
)

PUBLIC_COLUMNS = (
    PlanningApplication.id,
    PlanningApplication.source_object_id,
    PlanningApplication.planning_authority,
    PlanningApplication.application_number,
    PlanningApplication.description,
    PlanningApplication.address,
    PlanningApplication.postcode,
    PlanningApplication.application_status,
    PlanningApplication.application_type,
    PlanningApplication.decision,
    PlanningApplication.received_date,
    PlanningApplication.decision_date,
    PlanningApplication.grant_date,
    PlanningApplication.number_residential_units,
    PlanningApplication.floor_area,
    PlanningApplication.application_url,
    PlanningApplication.source_updated_at,
)


@router.get("", response_model=PlanningApplicationListResponse)
def list_planning_applications(
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    planning_authority: str | None = None,
    application_status: str | None = None,
    decision: str | None = None,
    received_from: date | None = None,
    received_to: date | None = None,
) -> PlanningApplicationListResponse:
    filters = []
    if planning_authority is not None:
        filters.append(PlanningApplication.planning_authority == planning_authority)
    if application_status is not None:
        filters.append(PlanningApplication.application_status == application_status)
    if decision is not None:
        filters.append(PlanningApplication.decision == decision)
    if received_from is not None:
        filters.append(PlanningApplication.received_date >= received_from)
    if received_to is not None:
        filters.append(PlanningApplication.received_date <= received_to)

    total = session.scalar(
        select(func.count(PlanningApplication.id)).where(*filters)
    ) or 0
    statement = (
        select(PlanningApplication)
        .options(load_only(*PUBLIC_COLUMNS))
        .where(*filters)
        .order_by(
            PlanningApplication.received_date.desc(),
            PlanningApplication.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    items = list(session.scalars(statement).all())

    return PlanningApplicationListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
    )
