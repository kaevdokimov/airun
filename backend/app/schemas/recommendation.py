from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecommendationContent(BaseModel):
    summary: str
    today_recommendation: str
    week_plan: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    progress_to_goal: str = ""


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    parsed: RecommendationContent | None = None
    context_snapshot: dict
    generated_at: datetime


class GenerateRecommendationResponse(BaseModel):
    success: bool
    recommendation: RecommendationResponse | None = None
    message: str = ""
