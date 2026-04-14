from datetime import datetime

from sqlalchemy import String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#Claim models

class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id"), index=True)
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    disruption_type: Mapped[str] = mapped_column(String(64))
    income_loss: Mapped[float] = mapped_column(Float)
    payout_amount: Mapped[float] = mapped_column(Float, default=0.0)
    premium_paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    premium_payment_id: Mapped[str] = mapped_column(String(96), default="")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    fraud_score: Mapped[float] = mapped_column(Float, default=0.0)
    fraud_notes: Mapped[str] = mapped_column(String(512), default="")
    payout_ref: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="claims")
    policy: Mapped["Policy"] = relationship(back_populates="claims")
