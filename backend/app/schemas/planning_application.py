from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from ..services.opportunity_scorer import (
    OpportunityLevel,
    OpportunityScoreBreakdown,
    OpportunityScoreComponent,
)
from ..services.planning_classifier import PlanningApplicationCategory


class PlanningApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_object_id: int
    planning_authority: str
    application_number: str
    description: str | None
    address: str | None
    postcode: str | None
    application_status: str | None
    application_type: str | None
    decision: str | None
    received_date: date | None
    decision_date: date | None
    grant_date: date | None
    number_residential_units: int | None
    floor_area: float | None
    application_url: str | None
    source_updated_at: datetime | None
    category: PlanningApplicationCategory
    opportunity_score: int
    opportunity_level: OpportunityLevel
    opportunity_breakdown: OpportunityScoreBreakdown
    opportunity_score_components: tuple[OpportunityScoreComponent, ...]


class PlanningApplicationListResponse(BaseModel):
    items: list[PlanningApplicationResponse]
    limit: int
    offset: int
    total: int


class PlanningApplicationCategorySummaryResponse(BaseModel):
    total: int
    categories: dict[PlanningApplicationCategory, int]


class NearbyPlanningApplicationResponse(PlanningApplicationResponse):
    distance_km: float


class NearbyPlanningApplicationListResponse(BaseModel):
    items: list[NearbyPlanningApplicationResponse]
    limit: int
    offset: int
    total: int
