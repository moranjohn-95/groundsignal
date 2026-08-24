from datetime import date

from pydantic import BaseModel

from ..services.opportunity_scorer import (
    OpportunityLevel,
    OpportunityScoreBreakdown,
    OpportunityScoreComponent,
)
from ..services.planning_classifier import PlanningApplicationCategory


class OpportunityResponse(BaseModel):
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
    distance_km: float
    opportunity_score: int
    opportunity_level: OpportunityLevel
    opportunity_breakdown: OpportunityScoreBreakdown
    opportunity_score_components: tuple[OpportunityScoreComponent, ...]


class OpportunityFeedResponse(BaseModel):
    items: list[OpportunityResponse]
    limit: int
    returned_count: int
