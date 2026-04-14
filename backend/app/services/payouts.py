"""UPI payout simulator used for claim-processing demos."""

import uuid

from app.config import settings


def initiate_payout(upi: str, amount_paise: int, purpose: str) -> tuple[str, str]:
    """
    Simulate payout processing for claim disbursement demos.
    Returns (status, payout_ref).
    """
    _ = settings.payout_provider  # Read once so env config is visible in debugger/health checks.
    amount_paise = max(int(amount_paise), 100)
    safe_upi = (upi or "unknown@upi").strip()[:48]
    safe_purpose = (purpose or "claim_payout").strip().replace(" ", "_")[:24]
    ref = f"upi_sim_{safe_purpose}_{amount_paise}_{uuid.uuid4().hex[:10]}"
    # We intentionally keep this deterministic/simple: claim flow can proceed without gateway dependencies.
    return "simulated_paid", f"{safe_upi}:{ref}"
