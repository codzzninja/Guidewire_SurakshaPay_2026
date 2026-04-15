from datetime import datetime
from pydantic import BaseModel


class ClaimOut(BaseModel):
    id: int
    event_id: str
    disruption_type: str
    income_loss: float
    payout_amount: float
    premium_paid_amount: float
    premium_payment_id: str
    status: str
    fraud_score: float
    fraud_notes: str
    payout_ref: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TriggerSimulateIn(BaseModel):
    zone_id: str | None = None
    force_mock_disruption: bool = False
    # Live path only: inject rain_trigger vs low metrics so fraud surfaces weather_integrity_risk.
    # Requires DEMO_WEATHER_EDGE_CASE=true or ALLOW_MOCKS=true on the API.
    demo_weather_integrity_mismatch: bool = False
