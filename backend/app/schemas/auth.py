from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class RegisterIn(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=6)
    full_name: str
    platform: str = Field(..., pattern="^(swiggy|zomato)$")
    zone_id: str
    upi_id: str
    avg_hours_per_day: float = 8.0
    lat: float = 13.04
    lon: float = 80.23
    consent_gps_location: bool = False
    consent_upi_account: bool = False
    consent_platform_activity: bool = False
    kyc_id_type: str = Field("pan", pattern="^(pan|aadhaar)$")
    kyc_document_last4: str = Field(..., min_length=4, max_length=4)

    @model_validator(mode="after")
    def _normalize_kyc_tail(self):
        t = (self.kyc_id_type or "pan").lower().strip()
        raw = (self.kyc_document_last4 or "").strip()
        if t == "aadhaar":
            if not raw.isdigit() or len(raw) != 4:
                raise ValueError("Aadhaar: enter last 4 digits only")
            self.kyc_document_last4 = raw
        else:
            u = raw.upper()
            if len(u) != 4 or not all(c.isalnum() for c in u):
                raise ValueError("PAN: enter last 4 characters (letters A–Z and digits 0–9)")
            self.kyc_id_type = "pan"
            self.kyc_document_last4 = u
        return self


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginIn(BaseModel):
    phone: str
    password: str


class UserOut(BaseModel):
    id: int
    phone: str
    full_name: str
    platform: str
    zone_id: str
    upi_id: str
    avg_hours_per_day: float
    lat: float
    lon: float
    gps_sample_count: int = 0
    gps_captured_at: str | None = None
    consent_gps_location: bool = False
    consent_upi_account: bool = False
    consent_platform_activity: bool = False
    active_days_last_365: int = 0
    kyc_id_type: str = "pan"
    kyc_document_last4: str = ""
    kyc_status: str = "pending"
    kyc_verified_at: datetime | None = None

    model_config = {"from_attributes": True}
