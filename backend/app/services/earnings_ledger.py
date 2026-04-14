"""Apply verified Razorpay payment amounts to daily earnings (baseline input)."""

import json
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.earning_day import EarningDay
from app.models.razorpay_payment import RazorpayPaymentRecord
from app.models.user import User


def sync_user_earnings_json_from_last7(db: Session, user: User) -> None:
    last7 = (
        db.query(EarningDay)
        .filter(EarningDay.user_id == user.id)
        .order_by(EarningDay.earn_date.desc())
        .limit(7)
        .all()
    )
    if len(last7) >= 7:
        asc7 = sorted(last7, key=lambda r: r.earn_date)
        user.earnings_json = json.dumps([r.amount for r in asc7])
        db.add(user)


def credit_today_from_payment(
    db: Session,
    user: User,
    *,
    payment_id: str,
    order_id: str,
    amount_paise: int,
) -> tuple[bool, str]:
    """
    Add payment amount to today's earning row (or create). Idempotent per payment_id.
    Returns (applied_new, message).
    """
    existing = (
        db.query(RazorpayPaymentRecord).filter(RazorpayPaymentRecord.payment_id == payment_id).first()
    )
    if existing:
        return False, "already_recorded"

    rupees = round(amount_paise / 100.0, 2)
    today = date.today()

    rec = RazorpayPaymentRecord(
        payment_id=payment_id,
        user_id=user.id,
        order_id=order_id,
        amount_paise=amount_paise,
    )
    db.add(rec)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False, "already_recorded"

    row = (
        db.query(EarningDay)
        .filter(EarningDay.user_id == user.id, EarningDay.earn_date == today)
        .first()
    )
    if row:
        row.amount = round(float(row.amount) + rupees, 2)
    else:
        db.add(
            EarningDay(
                user_id=user.id,
                earn_date=today,
                amount=rupees,
                minutes_online=None,
            )
        )

    sync_user_earnings_json_from_last7(db, user)
    db.commit()
    return True, "credited"
