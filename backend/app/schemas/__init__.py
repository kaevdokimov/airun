from app.schemas.auth import AuthTokenResponse, TelegramWebAuthRequest
from app.schemas.garmin import GarminConnectRequest, GarminMfaRequest, GarminStatusResponse, SyncResponse
from app.schemas.goal import GoalCreate, GoalResponse, GoalUpdate
from app.schemas.recommendation import (
    GenerateRecommendationResponse,
    RecommendationContent,
    RecommendationResponse,
)
from app.schemas.stats import ActivityResponse, DailySummaryResponse, WeekStatsResponse
from app.schemas.user import UserCreate, UserResponse

__all__ = [
    "ActivityResponse",
    "AuthTokenResponse",
    "DailySummaryResponse",
    "GarminConnectRequest",
    "GarminMfaRequest",
    "GarminStatusResponse",
    "GenerateRecommendationResponse",
    "GoalCreate",
    "GoalResponse",
    "GoalUpdate",
    "RecommendationContent",
    "RecommendationResponse",
    "SyncResponse",
    "TelegramWebAuthRequest",
    "UserCreate",
    "UserResponse",
    "WeekStatsResponse",
]
