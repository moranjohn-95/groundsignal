from datetime import date, datetime, timedelta, timezone
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
    PlanningApplicationCategorySummaryResponse,
    PlanningApplicationListResponse,
    PlanningApplicationResponse,
)
from ..services.application_urls import safe_application_url
from ..services.planning_classifier import (
    PLANNING_APPLICATION_CATEGORIES,
    PlanningApplicationCategory,
    classify_planning_application,
)
from ..services.opportunity_scorer import score_planning_application_opportunity


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


def _current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _planning_application_response(
    application: PlanningApplication,
) -> PlanningApplicationResponse:
    public_values = {
        column.key: getattr(application, column.key) for column in PUBLIC_COLUMNS
    }
    public_values["application_url"] = safe_application_url(
        public_values["application_url"]
    )
    category = classify_planning_application(
        description=application.description,
        application_type=application.application_type,
        number_residential_units=application.number_residential_units,
        floor_area=application.floor_area,
    )
    opportunity = score_planning_application_opportunity(
        description=application.description,
        application_type=application.application_type,
        number_residential_units=application.number_residential_units,
        floor_area=application.floor_area,
        received_date=application.received_date,
        category=category,
    )
    return PlanningApplicationResponse(
        **public_values,
        category=category,
        opportunity_score=opportunity.opportunity_score,
        opportunity_level=opportunity.opportunity_level,
        opportunity_breakdown=opportunity.score_breakdown,
        opportunity_score_components=opportunity.score_components,
    )


def _planning_application_filters(
    *,
    planning_authority: str | None = None,
    application_status: str | None = None,
    decision: str | None = None,
    received_from: date | None = None,
    received_to: date | None = None,
    category: PlanningApplicationCategory | None = None,
    recent_days: int | None = None,
) -> list[ColumnElement[bool]]:
    if recent_days is not None and received_from is not None:
        raise HTTPException(
            status_code=422,
            detail="recent_days cannot be combined with received_from.",
        )

    filters = []
    if planning_authority is not None:
        filters.append(PlanningApplication.planning_authority == planning_authority)
    if application_status is not None:
        filters.append(PlanningApplication.application_status == application_status)
    if decision is not None:
        filters.append(PlanningApplication.decision == decision)
    if recent_days is not None:
        cutoff = _current_utc_date() - timedelta(days=recent_days)
        filters.append(PlanningApplication.received_date >= cutoff)
    elif received_from is not None:
        filters.append(PlanningApplication.received_date >= received_from)
    if received_to is not None:
        filters.append(PlanningApplication.received_date <= received_to)
    if category is not None:
        filters.append(PlanningApplication.category == category)
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
    category: PlanningApplicationCategory | None = None,
    recent_days: Annotated[int | None, Query(ge=1, le=365)] = None,
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
        category=category,
        recent_days=recent_days,
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
            **_planning_application_response(application).model_dump(),
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


@router.get(
    "/categories/summary",
    response_model=PlanningApplicationCategorySummaryResponse,
)
def summarize_planning_application_categories(
    session: Annotated[Session, Depends(get_db)],
    planning_authority: str | None = None,
    application_status: str | None = None,
    decision: str | None = None,
    received_from: date | None = None,
    received_to: date | None = None,
    recent_days: Annotated[int | None, Query(ge=1, le=365)] = None,
) -> PlanningApplicationCategorySummaryResponse:
    filters = _planning_application_filters(
        planning_authority=planning_authority,
        application_status=application_status,
        decision=decision,
        received_from=received_from,
        received_to=received_to,
        recent_days=recent_days,
    )
    total = session.scalar(
        select(func.count(PlanningApplication.id)).where(*filters)
    ) or 0
    grouped_counts = session.execute(
        select(
            PlanningApplication.category,
            func.count(PlanningApplication.id),
        )
        .where(*filters)
        .group_by(PlanningApplication.category)
    ).all()

    categories = {
        category: 0 for category in PLANNING_APPLICATION_CATEGORIES
    }
    for category, count in grouped_counts:
        if category in categories:
            categories[category] = count

    return PlanningApplicationCategorySummaryResponse(
        total=total,
        categories=categories,
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

    return _planning_application_response(application)


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
    category: PlanningApplicationCategory | None = None,
    recent_days: Annotated[int | None, Query(ge=1, le=365)] = None,
) -> PlanningApplicationListResponse:
    filters = _planning_application_filters(
        planning_authority=planning_authority,
        application_status=application_status,
        decision=decision,
        received_from=received_from,
        received_to=received_to,
        category=category,
        recent_days=recent_days,
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
    items = [
        _planning_application_response(application)
        for application in session.scalars(statement).all()
    ]

    return PlanningApplicationListResponse(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
    )
