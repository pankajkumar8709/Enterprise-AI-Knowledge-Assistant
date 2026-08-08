from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth import authenticate_user, create_access_token_for_user, register_user

router = APIRouter()


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    return register_user(db, payload)


# @router.post("/login", response_model=TokenResponse)
# def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
#     user = authenticate_user(db, payload.email, payload.password)
#     if not user:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
#     return create_access_token_for_user(user)

from fastapi.security import OAuth2PasswordRequestForm

@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Username field will contain the email
    user = authenticate_user(
        db,
        form_data.username,
        form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    return create_access_token_for_user(user)


@router.get("/verify-token", response_model=UserRead)
def verify_token(current_user=Depends(get_current_user)) -> UserRead:
    return current_user
