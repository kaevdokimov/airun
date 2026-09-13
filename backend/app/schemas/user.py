from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
