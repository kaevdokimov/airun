from pydantic import BaseModel


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
