"""
auth.py – JWT authentication router.

Endpoints
---------
POST /auth/register – create a new user account.
POST /auth/login    – issue a Bearer JWT token (OAuth2 password flow).
GET  /auth/me       – return current user info (protected).
"""

from datetime import datetime, timedelta, timezone
from typing import Set

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext

from common.config import SECRET_KEY
from common.services.auth_audit import log_auth_event
from common.services.auth_dependency import ALGORITHM, get_current_user
from common.services.security import APIKeyChecker
from db.uow import TariffConsumptionUnitofWork
from middleware.rate_limit import auth_rate_limiter
from model.auth import RefreshTokenRequest, Token, UserCreate, UserPublic
from model.domain.user_model import User

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ACCESS_TOKEN_EXPIRE_HOURS: int = 12
REFRESH_TOKEN_EXPIRE_DAYS: int = 7

# Store invalidated refresh tokens (use Redis in production)
invalidated_refresh_tokens: Set[str] = set()

# ---------------------------------------------------------------------------
# Password hashing (bcrypt via passlib)
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Encode an access JWT with an expiry claim."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    payload = {"sub": subject, "exp": expire, "token_type": "access"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Encode a long-lived refresh JWT."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "token_type": "refresh"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])
require_register_key = APIKeyChecker(env_var="REGISTER_API_KEY")


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserCreate,
    is_authorized: bool = Security(require_register_key),
) -> UserPublic:
    """Create a new user account."""
    with TariffConsumptionUnitofWork() as uow:
        if uow.user_repository.get_by_username(payload.username):
            log_auth_event("register_username_exists", username=payload.username, success=False)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        user = User(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=payload.role.value,
        )
        uow.user_repository.add(user)
        uow.commit()
        log_auth_event("register_success", username=user.username, success=True)
        return UserPublic(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        )


@router.post("/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None
) -> Token:
    """Validate credentials and issue a JWT Bearer token with rate limiting."""
    # Rate limiting check
    client_ip = request.client.host if request else "unknown"
    if not auth_rate_limiter.check_rate_limit(f"login:{form_data.username}"):
        log_auth_event("login_rate_limited", username=form_data.username, success=False, 
                      details={"client_ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    with TariffConsumptionUnitofWork() as uow:
        user = uow.user_repository.get_by_username(form_data.username)
        if not user or not verify_password(form_data.password, user.hashed_password):
            log_auth_event("login_failed", username=form_data.username, success=False,
                          details={"client_ip": client_ip})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = create_access_token(
            subject=user.username,
            expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        )
        refresh_token = create_refresh_token(subject=user.username)
        log_auth_event("login_success", username=user.username, success=True,
                      details={"client_ip": client_ip})
        return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
def refresh_access_token(payload: RefreshTokenRequest) -> Token:
    """Issue a new access token (and rotate the refresh token) given a valid refresh token."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check if token was previously invalidated
    if payload.refresh_token in invalidated_refresh_tokens:
        log_auth_event("refresh_token_revoked", success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        decoded = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if decoded.get("token_type") != "refresh":
            raise credentials_error
        username: str | None = decoded.get("sub")
        if username is None:
            raise credentials_error
    except Exception:
        log_auth_event("refresh_token_invalid", success=False)
        raise credentials_error

    with TariffConsumptionUnitofWork() as uow:
        user = uow.user_repository.get_by_username(username)
        if user is None or not user.is_active:
            log_auth_event("refresh_token_user_inactive", username=username, success=False)
            raise credentials_error

    # Invalidate old refresh token (rotation)
    invalidated_refresh_tokens.add(payload.refresh_token)
    
    new_access_token = create_access_token(subject=username)
    new_refresh_token = create_refresh_token(subject=username)
    log_auth_event("refresh_token_success", username=username, success=True)
    return Token(access_token=new_access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    """Return public profile of the authenticated user."""
    return current_user
