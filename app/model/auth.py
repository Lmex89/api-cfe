from enum import Enum

from pydantic import BaseModel


class UserRole(str, Enum):
    admin = "admin"
    staff = "staff"
    user = "user"


# --- Request / Response models ---

class Token(BaseModel):
    """Returned by /auth/login on success."""
    access_token: str
    token_type: str = "bearer"


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
