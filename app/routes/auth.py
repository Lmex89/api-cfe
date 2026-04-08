"""
auth.py – JWT authentication router.

Endpoints
---------
POST /auth/register – create a new user account.
POST /auth/login    – issue a Bearer JWT token (OAuth2 password flow).
GET  /auth/me       – return current user info (protected).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext

from common.config import SECRET_KEY
from common.services.auth_dependency import ALGORITHM, get_current_user
from common.services.security import APIKeyChecker
from db.uow import TariffConsumptionUnitofWork
from model.auth import Token, UserCreate, UserPublic
from model.domain.user_model import User

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ACCESS_TOKEN_EXPIRE_HOURS: int = 12

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
    """Encode a JWT with an expiry claim."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    payload = {"sub": subject, "exp": expire}
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
        return UserPublic(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        )


@router.post("/login", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """Validate credentials and issue a JWT Bearer token."""
    with TariffConsumptionUnitofWork() as uow:
        user = uow.user_repository.get_by_username(form_data.username)
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = create_access_token(
            subject=user.username,
            expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        )
        return Token(access_token=token)


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    """Return public profile of the authenticated user."""
    return current_user
