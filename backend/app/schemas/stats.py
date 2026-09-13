from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    activity_type: str
    distance_m: float | None
    duration_sec: int | None
    started_at: datetime
    metrics: dict


class DailySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary_date: date
    stats: dict


class WeekStatsResponse(BaseModel):
    total_distance_m: float
    total_duration_sec: int
    activity_count: int
    activities: list[ActivityResponse]
