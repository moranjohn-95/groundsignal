from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal, cast as type_cast

from fastapi import APIRouter, Depends, Query
from geoalchemy2 import Geography
from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from ..dependencies import get_db
from ..models import PlanningApplication
from ..schemas import OpportunityFeedResponse, OpportunityResponse
from ..services.application_urls import safe_application_url
from ..services.opportunity_scorer import score_planning_application_opportunity
from ..services.planning_classifier import PlanningApplicationCategory
from ..services.rate_limiting import enforce_database_request_rate_limit


# Exact upstream terminal statuses observed in planning data. Deliberately avoid
# fuzzy "closed" matching because decided/finalised applications can be useful.
EXCLUDED_OPPORTUNITY_APPLICATION_STATUSES = (
    "Invalid - Case Closed",
    "Application Invalid",
    "INCOMPLETED APPLICATION",
    "WITHDRAWN",
)

router = APIRouter(
    prefix="/api/v1/opportunities",
    tags=["opportunities"],
    dependencies=[Depends(enforce_database_request_rate_limit)],
)

OpportunitySort = Literal["best", "nearest", "newest"]


@dataclass(frozen=True)
class OpportunityCandidate:
    id: int
    application_number: str
    planning_authority: str
    description: str | None
    address: str | None
    application_type: str | None
    application_status: str | None
    decision: str | None
    received_date: date | None
    application_url: str | None
    category: PlanningApplicationCategory
    number_residential_units: int | None
    floor_area: float | None
    distance_km: float


def _current_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _candidate_filters(
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    received_cutoff: date,
    category: PlanningApplicationCategory | None,
):
    search_point = cast(
        func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
        Geography(geometry_type="POINT", srid=4326),
    )
    within_radius = func.ST_DWithin(
        PlanningApplication.location,
        search_point,
        radius_km * 1000.0,
    )
    distance_km = (
        func.ST_Distance(PlanningApplication.location, search_point) / 1000.0
    ).label("distance_km")
    filters = [
        within_radius,
        PlanningApplication.received_date >= received_cutoff,
        PlanningApplication.category.is_not(None),
        or_(
            PlanningApplication.application_status.is_(None),
            PlanningApplication.application_status.not_in(
                EXCLUDED_OPPORTUNITY_APPLICATION_STATUSES
            ),
        ),
    ]
    if category is not None:
        filters.append(PlanningApplication.category == category)

    return filters, distance_km


def _candidate_statement(
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    received_cutoff: date,
    category: PlanningApplicationCategory | None,
    sort: OpportunitySort,
    page: int,
    page_size: int,
) -> Select:
    filters, distance_km = _candidate_filters(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        received_cutoff=received_cutoff,
        category=category,
    )

    statement = select(
        PlanningApplication.id,
        PlanningApplication.application_number,
        PlanningApplication.planning_authority,
        PlanningApplication.description,
        PlanningApplication.address,
        PlanningApplication.application_type,
        PlanningApplication.application_status,
        PlanningApplication.decision,
        PlanningApplication.received_date,
        PlanningApplication.application_url,
        PlanningApplication.category,
        PlanningApplication.number_residential_units,
        PlanningApplication.floor_area,
        distance_km,
    ).where(*filters)

    if sort == "nearest":
        statement = statement.order_by(
            distance_km.asc(),
            PlanningApplication.received_date.desc(),
            PlanningApplication.id.desc(),
        )
    elif sort == "newest":
        statement = statement.order_by(
            PlanningApplication.received_date.desc(),
            PlanningApplication.id.desc(),
        )
    else:
        # Best-opportunity order depends on the shared Python scorer, so every
        # filtered candidate must be scored before the requested page is sliced.
        return statement

    return statement.offset((page - 1) * page_size).limit(page_size)


def _candidate_count_statement(
    *,
    latitude: float,
    longitude: float,
    radius_km: float,
    received_cutoff: date,
    category: PlanningApplicationCategory | None,
) -> Select:
    filters, _ = _candidate_filters(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        received_cutoff=received_cutoff,
        category=category,
    )

    return select(func.count()).select_from(PlanningApplication).where(*filters)


def _load_candidates(
    session: Session,
    statement: Select,
) -> list[OpportunityCandidate]:
    rows = session.execute(statement).mappings().all()
    return [
        OpportunityCandidate(
            id=row["id"],
            application_number=row["application_number"],
            planning_authority=row["planning_authority"],
            description=row["description"],
            address=row["address"],
            application_type=row["application_type"],
            application_status=row["application_status"],
            decision=row["decision"],
            received_date=row["received_date"],
            application_url=row["application_url"],
            category=type_cast(PlanningApplicationCategory, row["category"]),
            number_residential_units=row["number_residential_units"],
            floor_area=row["floor_area"],
            distance_km=float(row["distance_km"]),
        )
        for row in rows
    ]


def _score_candidates(
    candidates: list[OpportunityCandidate],
    *,
    current_date: date,
) -> list[OpportunityResponse]:
    scored_candidates = []
    for candidate in candidates:
        opportunity = score_planning_application_opportunity(
            description=candidate.description,
            application_type=candidate.application_type,
            number_residential_units=candidate.number_residential_units,
            floor_area=candidate.floor_area,
            received_date=candidate.received_date,
            category=candidate.category,
            current_date=current_date,
        )
        scored_candidates.append(
            OpportunityResponse(
                id=candidate.id,
                application_number=candidate.application_number,
                planning_authority=candidate.planning_authority,
                description=candidate.description,
                address=candidate.address,
                application_type=candidate.application_type,
                application_status=candidate.application_status,
                decision=candidate.decision,
                received_date=candidate.received_date,
                application_url=safe_application_url(candidate.application_url),
                category=candidate.category,
                distance_km=candidate.distance_km,
                opportunity_score=opportunity.opportunity_score,
                raw_opportunity_score=opportunity.raw_opportunity_score,
                opportunity_level=opportunity.opportunity_level,
                opportunity_breakdown=opportunity.score_breakdown,
                opportunity_score_components=opportunity.score_components,
                electrical_work_brief=opportunity.electrical_work_brief,
            )
        )

    return scored_candidates


def _rank_best_candidates(
    candidates: list[OpportunityResponse],
) -> list[OpportunityResponse]:
    return sorted(
        candidates,
        key=lambda opportunity: (
            -opportunity.opportunity_score,
            -(
                opportunity.received_date.toordinal()
                if opportunity.received_date is not None
                else date.min.toordinal()
            ),
            -opportunity.id,
        ),
    )


@router.get("", response_model=OpportunityFeedResponse)
def list_opportunities(
    session: Annotated[Session, Depends(get_db)],
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=50)] = 25,
    recent_days: Annotated[int, Query(ge=1, le=365)] = 30,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: OpportunitySort = "best",
    category: PlanningApplicationCategory | None = None,
) -> OpportunityFeedResponse:
    """Return one globally sorted page of matching opportunities."""
    current_date = _current_utc_date()
    received_cutoff = current_date - timedelta(days=recent_days)
    statement = _candidate_statement(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        received_cutoff=received_cutoff,
        category=category,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    candidates = _load_candidates(session, statement)
    scored_candidates = _score_candidates(
        candidates,
        current_date=current_date,
    )

    if sort == "best":
        ranked_candidates = _rank_best_candidates(scored_candidates)
        total = len(ranked_candidates)
        page_start = (page - 1) * page_size
        items = ranked_candidates[page_start : page_start + page_size]
    else:
        count_statement = _candidate_count_statement(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            received_cutoff=received_cutoff,
            category=category,
        )
        total = session.scalar(count_statement) or 0
        items = scored_candidates

    return OpportunityFeedResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )
