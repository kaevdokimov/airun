from fastapi import APIRouter

from app.api.v1.routes import auth, garmin, goals, recommendations, stats, sync

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(garmin.router)
router.include_router(goals.router)
router.include_router(stats.router)
router.include_router(recommendations.router)
router.include_router(sync.router)
