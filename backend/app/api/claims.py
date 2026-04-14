from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.claim import Claim
from app.models.user import User
from app.schemas.claim import ClaimOut

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get("", response_model=list[ClaimOut])
def list_claims(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Claim).filter(Claim.user_id == user.id).order_by(Claim.id.desc()).limit(limit).all()
    return rows
