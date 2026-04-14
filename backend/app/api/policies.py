from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.policy import Policy, PolicyStatus
from app.models.user import User
from app.schemas.policy import PlanQuoteIn, PolicyOut, PremiumQuoteOut
from app.services.premium_xgb import quote_plan

router = APIRouter(prefix="/policies", tags=["policies"])


def _week_window() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


@router.post("/quote", response_model=PremiumQuoteOut)
async def quote(
    body: PlanQuoteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = await quote_plan(user, body.plan_type, db)
    return PremiumQuoteOut(**q)


@router.post("/subscribe", response_model=PolicyOut)
async def subscribe(body: PlanQuoteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    raise HTTPException(
        status_code=400,
        detail="Use Stripe weekly premium checkout to activate coverage",
    )


@router.get("/active", response_model=PolicyOut | None)
def active_policy(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    start, _ = _week_window()
    p = (
        db.query(Policy)
        .filter(
            Policy.user_id == user.id,
            Policy.status == PolicyStatus.active.value,
            Policy.payment_status == "paid",
            Policy.week_start == start,
        )
        .first()
    )
    return p
