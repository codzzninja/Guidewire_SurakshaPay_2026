"""Razorpay + Stripe payment flows for earnings demo and weekly premium activation."""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import razorpay
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from razorpay.errors import SignatureVerificationError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.services.environment_cache import get_or_refresh_env_rss
from app.models.policy import Policy, PolicyStatus
from app.models.user import User
from app.schemas.policy import PlanQuoteIn
from app.services.earnings_ledger import credit_today_from_payment
from app.services.payouts import initiate_payout
from app.services.premium_xgb import quote_plan

router = APIRouter(tags=["payments"])
STRIPE_PREMIUM_MIN_PAISE = 5_000  # ₹50; keeps above Stripe min (~$0.50 equivalent).


def _client() -> razorpay.Client:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=503,
            detail="Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET (Test mode) in backend/.env",
        )
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


class CreateOrderIn(BaseModel):
    amount_paise: int = Field(
        10_000,
        ge=100,
        description="Amount in paise (min ₹1). Default 10000 = ₹100.",
    )


class CreateOrderOut(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class SimulatePayoutIn(BaseModel):
    upi_id: str = Field(..., min_length=4, max_length=80)
    amount_paise: int = Field(..., ge=100, description="Amount in paise. 100 = ₹1")
    reason: str = Field("claim_payout", max_length=80)


@router.post("/payments/razorpay/order", response_model=CreateOrderOut)
def create_test_order(
    body: CreateOrderIn,
    user: User = Depends(get_current_user),
):
    """Create a Razorpay Order for Checkout (Test mode — no real money)."""
    client = _client()
    receipt = f"sp{user.id}_{uuid.uuid4().hex[:12]}"[:40]
    try:
        order = client.order.create(
            {
                "amount": body.amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": {
                    "suraksha_user_id": str(user.id),
                    "product": "suraksha_test_earning",
                },
            }
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Razorpay order failed: {e}") from e

    oid = order.get("id")
    if not oid:
        raise HTTPException(status_code=502, detail="Razorpay returned no order id")
    return CreateOrderOut(
        order_id=oid,
        amount=body.amount_paise,
        currency="INR",
        key_id=settings.razorpay_key_id,
    )


@router.post("/payments/simulate-payout")
def simulate_upi_payout(
    body: SimulatePayoutIn,
    user: User = Depends(get_current_user),
):
    """Manual UPI simulator API for demos/hackathons."""
    if getattr(user, "kyc_status", "pending") != "verified":
        raise HTTPException(
            status_code=400,
            detail="KYC required before payout simulation.",
        )
    status, payout_ref = initiate_payout(
        body.upi_id.strip(),
        int(body.amount_paise),
        f"manual_{body.reason.strip() or 'claim'}",
    )
    return {
        "ok": True,
        "processor": settings.payout_provider,
        "status": status,
        "payout_ref": payout_ref,
        "amount_inr": round(int(body.amount_paise) / 100.0, 2),
        "to_upi": body.upi_id.strip(),
        "requested_by_user_id": user.id,
        "note": "Simulation only: no real money moved.",
    }


@router.post("/payments/razorpay/verify")
def verify_checkout_payment(
    body: VerifyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Verify payment signature from Checkout `handler`, then credit today's earning.
    Use Test UPI e.g. success@razorpay in Razorpay Test mode.
    """
    client = _client()
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": body.razorpay_order_id,
                "razorpay_payment_id": body.razorpay_payment_id,
                "razorpay_signature": body.razorpay_signature,
            }
        )
    except SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid payment signature") from e

    try:
        order: dict[str, Any] = client.order.fetch(body.razorpay_order_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch order: {e}") from e

    notes = order.get("notes") or {}
    if str(notes.get("suraksha_user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="Order does not belong to this user")

    try:
        pay: dict[str, Any] = client.payment.fetch(body.razorpay_payment_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch payment: {e}") from e

    status = (pay.get("status") or "").lower()
    if status not in ("captured", "authorized"):
        raise HTTPException(status_code=400, detail=f"Payment not usable (status={status})")

    amount_paise = int(pay.get("amount") or 0)
    if amount_paise < 100:
        raise HTTPException(status_code=400, detail="Invalid payment amount")

    applied, msg = credit_today_from_payment(
        db,
        user,
        payment_id=body.razorpay_payment_id,
        order_id=body.razorpay_order_id,
        amount_paise=amount_paise,
    )
    amount_inr = round(amount_paise / 100.0, 2)
    return {
        "ok": True,
        "credited": applied,
        "message": msg,
        "amount_inr": amount_inr,
        "payment_id": body.razorpay_payment_id,
    }


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Optional: configure the same URL in Razorpay Dashboard → Webhooks (Test mode).
    Requires RAZORPAY_WEBHOOK_SECRET from the webhook settings page.
    """
    if not settings.razorpay_webhook_secret.strip():
        raise HTTPException(
            status_code=503,
            detail="Set RAZORPAY_WEBHOOK_SECRET to enable webhooks",
        )

    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature") or ""
    client = _client()
    try:
        client.utility.verify_webhook_signature(
            raw.decode("utf-8") if isinstance(raw, bytes) else raw,
            sig,
            settings.razorpay_webhook_secret.strip(),
        )
    except SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid webhook signature") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    event = data.get("event") or ""
    if event != "payment.captured":
        return {"ok": True, "ignored": event}

    pay_ent = (data.get("payload") or {}).get("payment", {}).get("entity") or {}
    payment_id = pay_ent.get("id")
    order_id = pay_ent.get("order_id")
    amount_paise = pay_ent.get("amount")
    if not payment_id or not order_id or amount_paise is None:
        raise HTTPException(status_code=400, detail="Webhook payload missing payment fields")

    try:
        order: dict[str, Any] = client.order.fetch(order_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not fetch order: {e}") from e

    notes = order.get("notes") or {}
    uid = notes.get("suraksha_user_id")
    if not uid:
        return {"ok": True, "skipped": "not_suraksha_order"}

    user = db.query(User).filter(User.id == int(uid)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User in order notes not found")

    apaise = int(amount_paise)
    applied, msg = credit_today_from_payment(
        db,
        user,
        payment_id=payment_id,
        order_id=order_id,
        amount_paise=apaise,
    )
    return {
        "ok": True,
        "credited": applied,
        "message": msg,
    }


# --- Stripe Checkout (Test mode: sk_test_...) — real gateway, no real money ---


class StripeCheckoutIn(BaseModel):
    amount_paise: int = Field(
        10_000,
        ge=100,
        description="Amount in paise (INR). Min ₹1.",
    )


def _stripe_configured() -> bool:
    return bool(settings.stripe_secret_key.strip())


def _week_window() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _sg(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stripe_line_item(amount_paise: int, *, name: str, description: str) -> list[dict[str, Any]]:
    return [
        {
            "price_data": {
                "currency": "inr",
                "unit_amount": int(amount_paise),
                "product_data": {
                    "name": name,
                    "description": description,
                },
            },
            "quantity": 1,
        }
    ]


@router.post("/payments/stripe/create-checkout-session")
def stripe_create_checkout(
    body: StripeCheckoutIn,
    user: User = Depends(get_current_user),
):
    """
    Hosted Stripe Checkout (Test mode). Redirect browser to returned `url`.
    After payment, user returns to frontend with ?stripe_session_id=...
    """
    if not _stripe_configured():
        raise HTTPException(
            status_code=503,
            detail="Set STRIPE_SECRET_KEY (sk_test_...) in backend/.env — https://dashboard.stripe.com/test/apikeys",
        )
    stripe.api_key = settings.stripe_secret_key.strip()
    base = settings.frontend_base_url.rstrip("/")
    success_url = f"{base}/?stripe_session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/?stripe_cancelled=1"
    amt = int(body.amount_paise)
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=_stripe_line_item(
                amt,
                name="SurakshaPay — test earning credit",
                description="Test mode — use card 4242424242424242",
            ),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"suraksha_user_id": str(user.id)},
            client_reference_id=str(user.id),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe Checkout failed: {e}") from e

    url = getattr(session, "url", None) or (session.get("url") if isinstance(session, dict) else None)
    sid = getattr(session, "id", None) or (session.get("id") if isinstance(session, dict) else None)
    if not url:
        raise HTTPException(status_code=502, detail="Stripe returned no checkout URL")
    return {"url": url, "session_id": sid}


class StripeVerifyIn(BaseModel):
    session_id: str = Field(..., min_length=10)


@router.post("/payments/stripe/verify-session")
def stripe_verify_session(
    body: StripeVerifyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Call after redirect from Stripe Checkout with ?stripe_session_id=..."""
    if not _stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe not configured")
    stripe.api_key = settings.stripe_secret_key.strip()
    try:
        sess = stripe.checkout.Session.retrieve(
            body.session_id,
            expand=["payment_intent"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid session: {e}") from e

    meta = _sg(sess, "metadata") or {}
    if not isinstance(meta, dict):
        try:
            meta = dict(meta) if meta is not None else {}
        except Exception:
            meta = {}
    if str(meta.get("suraksha_user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="This payment belongs to another account")

    if str(_sg(sess, "payment_status") or "").lower() != "paid":
        raise HTTPException(
            status_code=400,
            detail=f"Payment not complete (status={_sg(sess, 'payment_status')})",
        )

    amount_total = _sg(sess, "amount_total")
    if amount_total is None:
        raise HTTPException(status_code=400, detail="Session has no amount_total")
    amount_paise = int(amount_total)

    pi = _sg(sess, "payment_intent")
    if isinstance(pi, dict):
        payment_id = str(pi.get("id") or "")
    elif hasattr(pi, "id"):
        payment_id = str(pi.id)
    else:
        payment_id = str(_sg(sess, "id") or body.session_id)

    if not payment_id:
        payment_id = body.session_id

    applied, msg = credit_today_from_payment(
        db,
        user,
        payment_id=f"stripe_{payment_id}"[:64],
        order_id=str(_sg(sess, "id") or "")[:64],
        amount_paise=amount_paise,
    )
    amount_inr = round(amount_paise / 100.0, 2)
    return {
        "ok": True,
        "credited": applied,
        "message": msg,
        "amount_inr": amount_inr,
        "payment_id": payment_id,
    }


class StripePremiumCheckoutIn(BaseModel):
    plan_type: str = Field(..., pattern="^(basic|standard|pro)$")


@router.post("/payments/stripe/create-premium-session")
async def stripe_create_premium_checkout(
    body: StripePremiumCheckoutIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create Stripe Checkout for weekly premium payment."""
    if not (user.consent_gps_location and user.consent_upi_account and user.consent_platform_activity):
        raise HTTPException(
            status_code=400,
            detail="Consent required before premium purchase (GPS, UPI, platform activity).",
        )
    if getattr(user, "kyc_status", "pending") != "verified":
        raise HTTPException(
            status_code=400,
            detail="KYC required before premium purchase. Complete identity verification on your profile.",
        )
    if not _stripe_configured():
        raise HTTPException(
            status_code=503,
            detail="Set STRIPE_SECRET_KEY (sk_test_...) in backend/.env — https://dashboard.stripe.com/test/apikeys",
        )

    start, end = _week_window()
    existing_paid = (
        db.query(Policy)
        .filter(
            Policy.user_id == user.id,
            Policy.status == PolicyStatus.active.value,
            Policy.payment_status == "paid",
            Policy.week_start == start,
        )
        .first()
    )
    if existing_paid:
        raise HTTPException(status_code=400, detail="Weekly premium already paid for this week")

    # IRDAI-style adverse-selection control: lock enrollment while high-risk trigger is already active.
    if settings.enforce_lockout:
        try:
            env, rss, _ = await get_or_refresh_env_rss(db, user, force_refresh=False)
            w = env.get("weather") or {}
            a = env.get("aqi") or {}
            lockout_active = any(
                [
                    bool(w.get("rain_trigger")),
                    bool(w.get("heat_trigger")),
                    bool(a.get("severe_pollution")),
                    bool(rss.get("curfew_social")),
                    bool(rss.get("traffic_zone_closure")),
                ]
            )
            if lockout_active:
                raise HTTPException(
                    status_code=409,
                    detail="Enrollment lockout active during current disruption risk window. Try again after conditions normalize.",
                )
        except HTTPException:
            raise
        except Exception:
            # Do not block purchase if advisory data is temporarily unavailable.
            pass

    q = await quote_plan(user, body.plan_type, db)
    quoted_amount_paise = int(round(float(q["final_weekly_premium"]) * 100))
    amount_paise = max(STRIPE_PREMIUM_MIN_PAISE, quoted_amount_paise)
    stripe.api_key = settings.stripe_secret_key.strip()

    base = settings.frontend_base_url.rstrip("/")
    success_url = f"{base}/?stripe_premium_session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/?stripe_premium_cancelled=1"
    metadata = {
        "suraksha_user_id": str(user.id),
        "payment_kind": "weekly_premium",
        "plan_type": body.plan_type,
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "max_weekly_coverage": str(float(q["max_weekly_coverage"])),
        "max_per_event": str(float(q["max_per_event"])),
    }
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=_stripe_line_item(
                amount_paise,
                name=f"SurakshaPay weekly premium ({body.plan_type})",
                description=f"Coverage week {start.isoformat()} to {end.isoformat()}",
            ),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            client_reference_id=str(user.id),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe Checkout failed: {e}") from e

    url = _sg(session, "url")
    sid = _sg(session, "id")
    if not url:
        raise HTTPException(status_code=502, detail="Stripe returned no checkout URL")
    return {
        "url": url,
        "session_id": sid,
        "amount_paise": amount_paise,
        "quoted_amount_paise": quoted_amount_paise,
        "minimum_applied": amount_paise > quoted_amount_paise,
        "plan_type": body.plan_type,
    }


@router.post("/payments/stripe/verify-premium-session")
async def stripe_verify_premium_session(
    body: StripeVerifyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Verify Stripe premium payment and activate weekly policy."""
    if not _stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe not configured")
    stripe.api_key = settings.stripe_secret_key.strip()
    try:
        sess = stripe.checkout.Session.retrieve(body.session_id, expand=["payment_intent"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid session: {e}") from e

    meta = _sg(sess, "metadata") or {}
    if not isinstance(meta, dict):
        try:
            meta = dict(meta) if meta is not None else {}
        except Exception:
            meta = {}
    if str(meta.get("suraksha_user_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="This payment belongs to another account")
    if str(meta.get("payment_kind") or "") != "weekly_premium":
        raise HTTPException(status_code=400, detail="Not a weekly premium payment session")
    if str(_sg(sess, "payment_status") or "").lower() != "paid":
        raise HTTPException(
            status_code=400,
            detail=f"Payment not complete (status={_sg(sess, 'payment_status')})",
        )

    amount_total = _sg(sess, "amount_total")
    if amount_total is None:
        raise HTTPException(status_code=400, detail="Session has no amount_total")
    amount_paise = int(amount_total)

    plan_type = str(meta.get("plan_type") or "").strip()
    if plan_type not in ("basic", "standard", "pro"):
        raise HTTPException(status_code=400, detail="Premium session missing valid plan")

    week_start_iso = str(meta.get("week_start") or "")
    week_end_iso = str(meta.get("week_end") or "")
    try:
        week_start = date.fromisoformat(week_start_iso)
        week_end = date.fromisoformat(week_end_iso)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Premium session has invalid week window") from e

    pi = _sg(sess, "payment_intent")
    payment_id = str(_sg(pi, "id") or _sg(sess, "id") or body.session_id)

    existing_by_payment = (
        db.query(Policy)
        .filter(
            Policy.user_id == user.id,
            Policy.premium_payment_id == payment_id,
            Policy.payment_status == "paid",
        )
        .first()
    )
    if existing_by_payment:
        return {
            "ok": True,
            "activated": False,
            "message": "already_activated",
            "policy_id": existing_by_payment.id,
            "amount_inr": round(amount_paise / 100.0, 2),
            "payment_id": payment_id,
        }

    existing_week_paid = (
        db.query(Policy)
        .filter(
            Policy.user_id == user.id,
            Policy.week_start == week_start,
            Policy.status == PolicyStatus.active.value,
            Policy.payment_status == "paid",
        )
        .first()
    )
    if existing_week_paid:
        return {
            "ok": True,
            "activated": False,
            "message": "already_paid_this_week",
            "policy_id": existing_week_paid.id,
            "amount_inr": round(amount_paise / 100.0, 2),
            "payment_id": payment_id,
        }

    q = await quote_plan(user, plan_type, db)
    quoted_premium = round(float(q["final_weekly_premium"]), 2)
    # Product choice: keep a single premium number in app records (AI-adjusted weekly premium).
    paid_amount = quoted_premium
    p = Policy(
        user_id=user.id,
        plan_type=plan_type,
        weekly_premium=quoted_premium,
        max_weekly_coverage=float(q["max_weekly_coverage"]),
        max_per_event=float(q["max_per_event"]),
        status=PolicyStatus.active.value,
        payment_status="paid",
        payment_provider="stripe",
        premium_payment_id=payment_id[:96],
        premium_paid_amount=paid_amount,
        premium_paid_at=datetime.now(timezone.utc),
        week_start=week_start,
        week_end=week_end,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return {
        "ok": True,
        "activated": True,
        "message": "activated",
        "policy_id": p.id,
        "amount_inr": paid_amount,
        "payment_id": payment_id,
    }
