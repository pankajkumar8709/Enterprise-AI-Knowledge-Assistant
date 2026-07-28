from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter()


@router.get("/me", response_model=UserRead)
def read_me(current_user=Depends(get_current_user)) -> UserRead:
    return current_user


@router.get("", response_model=List[UserRead])
def list_users(
    db: Session = Depends(get_db), current_user=Depends(get_current_active_admin)
) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()
