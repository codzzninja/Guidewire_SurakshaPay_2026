from pydantic import BaseModel, Field


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

    model_config = {"from_attributes": True}
