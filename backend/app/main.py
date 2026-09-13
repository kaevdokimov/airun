import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.middleware import RequestIdFilter, request_id_middleware
from app.api.v1.router import router
from app.config import get_settings
from app.database import engine
from app.limiter import limiter
from app.services.ai.factory import log_llm_startup_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [request_id=%(request_id)s] [%(name)s] %(message)s",
)
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not settings.internal_bot_secret:
        raise RuntimeError("INTERNAL_BOT_SECRET is required")
    if not settings.credentials_encryption_key:
        raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY is required")
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is required")
    log_llm_startup_status()
    logger.info("AIRun API starting")
    yield
    await engine.dispose()
    logger.info("AIRun API stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

    app = FastAPI(title="AIRun API", version="0.1.0", lifespan=lifespan)
    app.middleware("http")(request_id_middleware)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.get("/health")
    @limiter.limit("60/minute")
    async def health(request: Request):
        return {"status": "ok", "service": "airun-api"}

    @app.get("/ready")
    @limiter.limit("60/minute")
    async def ready(request: Request):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ready", "database": "ok"}
        except Exception as exc:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": str(exc)},
            )

    return app


app = create_app()
