from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import GoalDistance, GoalStatus


class GoalCreate(BaseModel):
    distance: GoalDistance
    target_time_seconds: int | None = None
    race_date: date


class GoalUpdate(BaseModel):
    distance: GoalDistance | None = None
    target_time_seconds: int | None = None
    race_date: date | None = None
    status: GoalStatus | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    distance: GoalDistance
    target_time_seconds: int | None
    race_date: date
    status: GoalStatus
    days_until_race: int = 0
