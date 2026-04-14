"""Cached OpenWeather + WAQI + RSS bundle per user for pricing and /monitoring/live."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EnvironmentSnapshot(Base):
    __tablename__ = "environment_snapshots"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="environment_snapshot")
