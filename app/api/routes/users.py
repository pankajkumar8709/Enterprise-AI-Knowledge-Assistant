from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_admin, get_current_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import AdminUserCreate, UserRead
from app.services.audit import record_audit
from app.services.auth import create_admin_user

router = APIRouter()


class UserPatch(BaseModel):
    role: UserRole | None = None
    department_id: int | None = Field(default=None)
    is_active: bool | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    clear_department: bool = False


@router.get("/me", response_model=UserRead, status_code=status.HTTP_200_OK)
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("", response_model=list[UserRead], status_code=status.HTTP_200_OK)
def list_users(db: Session = Depends(get_db), current_user=Depends(get_current_active_admin)) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> User:
    user = create_admin_user(db, payload)
    record_audit(
        db,
        action="user.create",
        entity_type="user",
        entity_id=str(user.id),
        user_id=current_user.id,
        metadata={"role": user.role.value, "department_id": user.department_id},
        ip=request.client.host if request.client else None,
    )
    return user


@router.patch("/{user_id}", response_model=UserRead, status_code=status.HTTP_200_OK)
def update_user(
    user_id: int,
    payload: UserPatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_admin),
) -> User:
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changes: dict[str, object] = {}
    if payload.role is not None:
        target.role = payload.role
        changes["role"] = payload.role.value
    if payload.clear_department:
        target.department_id = None
        changes["department_id"] = None
    elif payload.department_id is not None:
        target.department_id = payload.department_id
        changes["department_id"] = payload.department_id
    if payload.is_active is not None:
        target.is_active = payload.is_active
        changes["is_active"] = payload.is_active
    if payload.full_name is not None:
        target.full_name = payload.full_name
        changes["full_name"] = payload.full_name

    db.add(target)
    db.commit()
    db.refresh(target)
    record_audit(
        db,
        action="user.update",
        entity_type="user",
        entity_id=str(target.id),
        user_id=current_user.id,
        metadata={"changes": changes},
        ip=request.client.host if request.client else None,
    )
    return target
