from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session, load_only
from sqlalchemy.sql.elements import ColumnElement

from ..dependencies import get_db
from ..models import PlanningApplication
from ..schemas import (
    NearbyPlanningApplicationListResponse,
    NearbyPlanningApplicationResponse,
    PlanningApplicationListResponse,
    PlanningApplicationResponse,
)


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


def _planning_application_filters(
    *,
    planning_authority: str | None = None,
    application_status: str | None = None,
    decision: str | None = None,
    received_from: date | None = None,
    received_to: date | None = None,
) -> list[ColumnElement[bool]]:
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
    return filters


@router.get("/nearby", response_model=NearbyPlanningApplicationListResponse)
def list_nearby_planning_applications(
    session: Annotated[Session, Depends(get_db)],
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=50)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    received_from: date | None = None,
    received_to: date | None = None,
    application_status: str | None = None,
    decision: str | None = None,
) -> NearbyPlanningApplicationListResponse:
    search_point = cast(
        func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
        Geography(geometry_type="POINT", srid=4326),
    )
    radius_metres = radius_km * 1000.0
    within_radius = func.ST_DWithin(
        PlanningApplication.location,
        search_point,
        radius_metres,
    )
    distance_km = (
        func.ST_Distance(PlanningApplication.location, search_point) / 1000.0
    ).label("distance_km")
    filters = _planning_application_filters(
        application_status=application_status,
        decision=decision,
        received_from=received_from,
        received_to=received_to,
    )

    total = session.scalar(
        select(func.count(PlanningApplication.id)).where(within_radius, *filters)
    ) or 0
    statement = (
        select(PlanningApplication, distance_km)
        .options(load_only(*PUBLIC_COLUMNS))
        .where(within_radius, *filters)
        .order_by(distance_km.asc(), PlanningApplication.id.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = session.execute(statement).all()
    items = [
        NearbyPlanningApplicationResponse(
            **PlanningApplicationResponse.model_validate(application).model_dump(),
            distance_km=float(distance),
        )
        for application, distance in rows
    ]

    return NearbyPlanningApplicationListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get("/{application_id}", response_model=PlanningApplicationResponse)
def get_planning_application(
    session: Annotated[Session, Depends(get_db)],
    application_id: Annotated[int, Path(gt=0)],
) -> PlanningApplicationResponse:
    application = session.scalar(
        select(PlanningApplication)
        .options(load_only(*PUBLIC_COLUMNS))
        .where(PlanningApplication.id == application_id)
    )
    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Planning application not found.",
        )

    return PlanningApplicationResponse.model_validate(application)


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
    filters = _planning_application_filters(
        planning_authority=planning_authority,
        application_status=application_status,
        decision=decision,
        received_from=received_from,
        received_to=received_to,
    )

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
