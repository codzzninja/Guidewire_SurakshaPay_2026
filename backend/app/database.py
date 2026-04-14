from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sqlite_add_column_if_missing(table: str, column: str, ddl: str) -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        names = {r[1] for r in rows}
        if column not in names:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            conn.commit()


def init_db():
    import app.models  # noqa: F401 — register all ORM tables on Base.metadata
    Base.metadata.create_all(bind=engine)
    _sqlite_add_column_if_missing("users", "gps_attestation_json", "gps_attestation_json TEXT DEFAULT '{}'")
    _sqlite_add_column_if_missing("users", "consent_gps_location", "consent_gps_location BOOLEAN DEFAULT 0")
    _sqlite_add_column_if_missing("users", "consent_upi_account", "consent_upi_account BOOLEAN DEFAULT 0")
    _sqlite_add_column_if_missing("users", "consent_platform_activity", "consent_platform_activity BOOLEAN DEFAULT 0")
    _sqlite_add_column_if_missing("users", "consent_version", "consent_version TEXT DEFAULT 'v1'")
    _sqlite_add_column_if_missing("users", "consent_captured_at", "consent_captured_at DATETIME")
    _sqlite_add_column_if_missing("users", "active_days_last_365", "active_days_last_365 INTEGER DEFAULT 0")
    _sqlite_add_column_if_missing("users", "kyc_id_type", "kyc_id_type TEXT DEFAULT 'pan'")
    _sqlite_add_column_if_missing("users", "kyc_document_last4", "kyc_document_last4 TEXT DEFAULT ''")
    _sqlite_add_column_if_missing("users", "kyc_status", "kyc_status TEXT DEFAULT 'pending'")
    _sqlite_add_column_if_missing("users", "kyc_verified_at", "kyc_verified_at DATETIME")
    _sqlite_add_column_if_missing("policies", "payment_status", "payment_status TEXT DEFAULT 'unpaid'")
    _sqlite_add_column_if_missing("policies", "payment_provider", "payment_provider TEXT DEFAULT ''")
    _sqlite_add_column_if_missing("policies", "premium_payment_id", "premium_payment_id TEXT DEFAULT ''")
    _sqlite_add_column_if_missing("policies", "premium_paid_amount", "premium_paid_amount FLOAT DEFAULT 0")
    _sqlite_add_column_if_missing("policies", "premium_paid_at", "premium_paid_at DATETIME")
    _sqlite_add_column_if_missing("claims", "premium_paid_amount", "premium_paid_amount FLOAT DEFAULT 0")
    _sqlite_add_column_if_missing("claims", "premium_payment_id", "premium_payment_id TEXT DEFAULT ''")
