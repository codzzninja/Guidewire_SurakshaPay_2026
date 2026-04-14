from datetime import datetime

from sqlalchemy import String, Float, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    platform: Mapped[str] = mapped_column(String(32))  # swiggy | zomato
    zone_id: Mapped[str] = mapped_column(String(64), index=True)
    upi_id: Mapped[str] = mapped_column(String(120))
    avg_hours_per_day: Mapped[float] = mapped_column(Float, default=8.0)
    lat: Mapped[float] = mapped_column(Float, default=13.04)
    lon: Mapped[float] = mapped_column(Float, default=80.23)
    earnings_json: Mapped[str] = mapped_column(
        Text,
        default='[780, 800, 810, 795, 820, 805, 800]',
    )
    # Last device GPS attestation (samples + MSTS features) — JSON string
    gps_attestation_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    policies: Mapped[list["Policy"]] = relationship(back_populates="user")
    claims: Mapped[list["Claim"]] = relationship(back_populates="user")
    earning_days: Mapped[list["EarningDay"]] = relationship(back_populates="user")
    environment_snapshot: Mapped["EnvironmentSnapshot | None"] = relationship(
        back_populates="user",
        uselist=False,
    )
