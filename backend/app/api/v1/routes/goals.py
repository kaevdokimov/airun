from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_telegram_id
from app.api.v1.routes.common import get_user_by_telegram, goal_to_response
from app.database import get_db
from app.models import Goal
from app.schemas import GoalCreate, GoalResponse, GoalUpdate
from app.utils.timezone import user_today

router = APIRouter(prefix="/goals")


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(select(Goal).where(Goal.user_id == user.id).order_by(Goal.race_date))
    return [goal_to_response(g, user.timezone) for g in result.scalars().all()]


@router.post("", response_model=GoalResponse)
async def create_goal(
    payload: GoalCreate,
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    if payload.race_date < user_today(user.timezone):
        raise HTTPException(status_code=400, detail="Дата забега должна быть в будущем")
    goal = Goal(
        user_id=user.id,
        distance=payload.distance,
        target_time_seconds=payload.target_time_seconds,
        race_date=payload.race_date,
    )
    db.add(goal)
    await db.flush()
    return goal_to_response(goal, user.timezone)


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    payload: GoalUpdate,
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.flush()
    return goal_to_response(goal, user.timezone)


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: UUID,
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(get_authenticated_telegram_id),
):
    user = await get_user_by_telegram(db, telegram_id)
    result = await db.execute(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id))
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.delete(goal)
    return {"status": "deleted"}
