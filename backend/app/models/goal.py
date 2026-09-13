from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.recommendation import Recommendation
    from app.models.user import User


class GoalDistance(str, enum.Enum):
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF = "half"
    MARATHON = "marathon"


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


DISTANCE_METERS = {
    GoalDistance.FIVE_K: 5000,
    GoalDistance.TEN_K: 10000,
    GoalDistance.HALF: 21097,
    GoalDistance.MARATHON: 42195,
}


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    distance: Mapped[GoalDistance] = mapped_column(Enum(GoalDistance, name="goal_distance"))
    target_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    race_date: Mapped[date] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(Enum(GoalStatus, name="goal_status"), default=GoalStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="goals")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="goal")
