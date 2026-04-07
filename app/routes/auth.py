"""
auth.py – JWT authentication router.

Endpoints
---------
POST /auth/login  – issue a Bearer JWT token (OAuth2 password flow).
GET  /auth/me     – return current user info (protected).
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from model.auth import Token, UserInDB, UserPublic

# ---------------------------------------------------------------------------
# Security constants
# ---------------------------------------------------------------------------

# A fresh cryptographically-strong key is generated at startup.
# In production, load this from an environment variable / secrets manager.
SECRET_KEY: str = secrets.token_hex(32)
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

# ---------------------------------------------------------------------------
# Password hashing (bcrypt via passlib)
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# In-memory user store (demo only – replace with a real DB in production)
# ---------------------------------------------------------------------------

_FAKE_USERS: dict[str, UserInDB] = {
    "alice": UserInDB(
        username="alice",
        email="alice@example.com",
        full_name="Alice Example",
        hashed_password=hash_password("supersecret"),
    )
}


def get_user(username: str) -> UserInDB | None:
    return _FAKE_USERS.get(username)


def authenticate_user(username: str, password: str) -> UserInDB | None:
    user = get_user(username)
    if user and verify_password(password, user.hashed_password):
        return user
    return None


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Encode a JWT with an expiry claim."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# OAuth2 scheme – points Swagger UI at the login endpoint
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    """Decode the Bearer token and return the authenticated user."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = get_user(username)
    if user is None:
        raise credentials_error

    return UserPublic(**user.model_dump())


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """Validate credentials and issue a JWT Bearer token."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        subject=user.username,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token)


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    """Return public profile of the authenticated user."""
    return current_user
