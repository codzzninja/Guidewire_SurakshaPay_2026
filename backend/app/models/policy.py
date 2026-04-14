from datetime import datetime, date

from sqlalchemy import String, Float, DateTime, ForeignKey, Date, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class PlanType(str, enum.Enum):
    basic = "basic"
    standard = "standard"
    pro = "pro"


class PolicyStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_type: Mapped[str] = mapped_column(String(16))
    weekly_premium: Mapped[float] = mapped_column(Float)
    max_weekly_coverage: Mapped[float] = mapped_column(Float)
    max_per_event: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default=PolicyStatus.active.value)
    payment_status: Mapped[str] = mapped_column(String(16), default="unpaid")
    payment_provider: Mapped[str] = mapped_column(String(16), default="")
    premium_payment_id: Mapped[str] = mapped_column(String(96), default="")
    premium_paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    premium_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    week_start: Mapped[date] = mapped_column(Date)
    week_end: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="policies")
    claims: Mapped[list["Claim"]] = relationship(back_populates="policy")
