from datetime import datetime

from sqlalchemy import String, Float, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    zone_id: Mapped[str] = mapped_column(String(64), index=True)
    disruption_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[float] = mapped_column(Float, default=0.0)
    external_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[str] = mapped_column(String(2048), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
