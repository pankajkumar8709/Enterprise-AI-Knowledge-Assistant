import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class UserCreate(UserBase):
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must include at least one uppercase letter and one digit")
        return value


class UserRead(UserBase):
    id: int
    role: UserRole
    is_active: bool
    department_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminUserCreate(UserCreate):
    """POST /users body (admin, spec §8): arbitrary role + department."""

    role: UserRole = UserRole.EMPLOYEE
    department_id: int | None = None
