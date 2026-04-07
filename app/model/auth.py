from pydantic import BaseModel


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


class UserInDB(UserPublic):
    """Internal user record that includes the hashed password."""
    hashed_password: str
