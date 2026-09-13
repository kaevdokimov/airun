from pydantic import BaseModel, Field


class GarminConnectRequest(BaseModel):
    telegram_id: int
    email: str = Field(
        min_length=5,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=6, max_length=256)


class GarminMfaRequest(BaseModel):
    telegram_id: int
    mfa_code: str = Field(min_length=1, max_length=32)


class GarminStatusResponse(BaseModel):
    connected: bool
    email: str | None = None
    last_error: str | None = None


class SyncResponse(BaseModel):
    success: bool
    activities_synced: int = 0
    summaries_synced: int = 0
    message: str = ""
