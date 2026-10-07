"""Synchronize the one env-managed administrator account at application startup."""

from __future__ import annotations

import logging
import re

from passlib.exc import UnknownHashError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def sync_configured_admin(db: Session) -> User | None:
    """Create or update the bootstrap admin from ADMIN_EMAIL and ADMIN_PASSWORD.

    An email change updates the marked bootstrap account in place. A collision
    with a different user's email fails startup rather than taking over that user.
    """

    email = settings.admin_email.strip().lower()
    password = settings.admin_password.get_secret_value()
    if not email and not password:
        return None
    if not email or not password:
        raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must both be configured")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise RuntimeError("ADMIN_EMAIL must be a valid email address")
    if len(password) < 10 or not re.search(r"[A-Z]", password) or not re.search(r"\d", password):
        raise RuntimeError("ADMIN_PASSWORD must be at least 10 characters with an uppercase letter and a digit")
    if len(password.encode("utf-8")) > 72:
        raise RuntimeError("ADMIN_PASSWORD exceeds the configured bcrypt byte limit")

    try:
        admin = db.query(User).filter(User.is_bootstrap_admin.is_(True)).one_or_none()
        email_owner = db.query(User).filter(func.lower(User.email) == email).one_or_none()
        if email_owner is not None and admin is not None and email_owner.id != admin.id:
            raise RuntimeError("ADMIN_EMAIL is already assigned to a different user")

        user = admin or email_owner
        if user is None:
            user = User(
                full_name="Administrator",
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
                is_bootstrap_admin=True,
            )
            db.add(user)
            db.flush()
        else:
            credentials_changed = user.email.lower() != email
            if not credentials_changed:
                try:
                    credentials_changed = not verify_password(password, user.hashed_password)
                except UnknownHashError:
                    credentials_changed = True

            if credentials_changed:
                user.email = email
                user.hashed_password = hash_password(password)
                db.query(RefreshToken).filter(
                    RefreshToken.user_id == user.id,
                    RefreshToken.revoked.is_(False),
                ).update({RefreshToken.revoked: True}, synchronize_session=False)

            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_bootstrap_admin = True
            db.add(user)

        db.commit()
        db.refresh(user)
        logger.info("Synchronized env-managed administrator account id=%s", user.id)
        return user
    except Exception:
        db.rollback()
        raise
