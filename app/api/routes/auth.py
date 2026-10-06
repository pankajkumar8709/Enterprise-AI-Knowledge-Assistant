from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.audit import record_audit
from app.services.auth import (
    authenticate_user,
    issue_token_pair,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter()


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    user = register_user(db, payload)
    record_audit(
        db,
        action="user.create",
        entity_type="user",
        entity_id=str(user.id),
        user_id=user.id,
        ip=request.client.host if request.client else None,
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        payload = LoginRequest.model_validate(await request.json())
        email = payload.email
        password = payload.password
    else:
        form = await request.form()
        email = str(form.get("username") or form.get("email") or "")
        password = str(form.get("password") or "")
        if not email or not password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Email/username and password are required",
            )

    user = authenticate_user(db, str(email), str(password))

    if not user:
        record_audit(
            db,
            action="auth.login_failed",
            entity_type="user",
            entity_id=str(email),
            ip=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token_response = issue_token_pair(db, user)
    record_audit(
        db,
        action="auth.login",
        entity_type="user",
        entity_id=str(user.id),
        user_id=user.id,
        ip=request.client.host if request.client else None,
    )
    return token_response


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return rotate_refresh_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, request: Request, db: Session = Depends(get_db)) -> None:
    revoked = revoke_refresh_token(db, payload.refresh_token)
    record_audit(
        db,
        action="auth.logout",
        entity_type="refresh_token",
        entity_id="revoked" if revoked else "unknown",
        ip=request.client.host if request.client else None,
    )


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/verify-token", response_model=UserRead)
def verify_token(current_user: User = Depends(get_current_user)) -> User:
    return current_user
