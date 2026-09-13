from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import GoalDistance, GoalStatus


class UserCreate(BaseModel):
    telegram_id: int
    timezone: str = "Europe/Moscow"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    telegram_id: int
    timezone: str
    last_synced_at: datetime | None
    created_at: datetime
    has_garmin: bool = False


class GarminConnectRequest(BaseModel):
    telegram_id: int
    email: str
    password: str


class GarminMfaRequest(BaseModel):
    telegram_id: int
    mfa_code: str


class GarminStatusResponse(BaseModel):
    connected: bool
    email: str | None = None
    last_error: str | None = None


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


class SyncResponse(BaseModel):
    success: bool
    activities_synced: int = 0
    summaries_synced: int = 0
    message: str = ""


class GenerateRecommendationResponse(BaseModel):
    success: bool
    recommendation: RecommendationResponse | None = None
    message: str = ""


class TelegramWebAuthRequest(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class AuthTokenResponse(BaseModel):
    access_token: str
    telegram_id: int
    token_type: str = "bearer"
