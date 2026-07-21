import re
from enum import Enum

from pydantic import BaseModel, field_validator


class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"
    user = "user"


# --- Request / Response models ---

class Token(BaseModel):
    """Returned by /auth/login and /auth/refresh on success."""
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Payload for POST /auth/refresh."""
    refresh_token: str


class UserPublic(BaseModel):
    """Safe user representation returned by /auth/me (no password)."""
    username: str
    email: str | None = None
    full_name: str | None = None
    role: UserRole = UserRole.user


class UserInDB(UserPublic):
    """Internal user record that includes the hashed password."""
    hashed_password: str


class UserCreate(BaseModel):
    """Payload for POST /auth/register."""
    username: str
    password: str
    email: str | None = None
    full_name: str | None = None
    role: UserRole = UserRole.user

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"[a-z]", v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r"[0-9]", v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r"[@$!%*?&#]", v):
            raise ValueError('Password must contain at least one special character (@$!%*?&#)')
        return v
