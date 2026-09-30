from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .planning_application import PlanningApplicationResponse


class SaveOpportunityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planning_application_id: int = Field(gt=0)


class SavedOpportunityResponse(BaseModel):
    id: int
    saved_at: datetime
    opportunity: PlanningApplicationResponse


class SavedOpportunityListResponse(BaseModel):
    items: list[SavedOpportunityResponse]
    limit: int
    offset: int
    total: int
