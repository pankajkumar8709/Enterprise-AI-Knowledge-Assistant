import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from passlib.exc import UnknownHashError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.auth import TokenResponse, TokenUser

logger = logging.getLogger(__name__)


def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def register_user(db: Session, payload) -> User:
    normalized_email = str(payload.email).lower()

    if not settings.allow_self_signup:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Self signup is disabled")
    allowed_domains = settings.allowed_email_domain_list
    if allowed_domains and normalized_email.rsplit("@", 1)[-1] not in allowed_domains:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email domain not allowed")

    existing_user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        full_name=payload.full_name,
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        # Public signup always creates an employee. Admin assignment is an admin-only operation.
        role=UserRole.EMPLOYEE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_admin_user(db: Session, payload) -> User:
    """POST /users (admin) — arbitrary role + department (spec §8)."""

    normalized_email = str(payload.email).lower()
    existing_user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    from app.models.department import Department

    if payload.department_id is not None:
        department = db.query(Department).filter(Department.id == payload.department_id).first()
        if department is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown department_id")

    user = User(
        full_name=payload.full_name,
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        department_id=payload.department_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    if not user or not user.is_active:
        return None

    try:
        password_matches = verify_password(password, user.hashed_password)
    except UnknownHashError:
        logger.error("User %s has an unrecognized password hash; password reset is required", user.id)
        return None

    if not password_matches:
        return None
    return user


def issue_token_pair(db: Session, user: User) -> TokenResponse:
    """Access + refresh tokens; only the refresh hash is persisted (spec §5)."""

    raw_refresh = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(raw_refresh),
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_days),
        )
    )
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.email, user.role.value),
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
        user=TokenUser(id=user.id, email=user.email, full_name=user.full_name, role=user.role.value),
    )


def rotate_refresh_token(db: Session, raw_token: str) -> TokenResponse:
    """Consume a valid refresh token and issue a new pair (old revoked: rotation)."""

    token_hash = _hash_refresh_token(raw_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if stored is None or stored.revoked or stored.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = db.query(User).filter(User.id == stored.user_id).first()
    if user is None or not user.is_active:
        stored.revoked = True
        db.add(stored)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    stored.revoked = True
    db.add(stored)
    db.commit()
    return issue_token_pair(db, user)


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    token_hash = _hash_refresh_token(raw_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if stored is None or stored.revoked:
        return False
    stored.revoked = True
    db.add(stored)
    db.commit()
    return True
