"""
Shared FastAPI dependency for JWT Bearer authentication.

Import `get_current_user` into any router to require a valid JWT on all
its endpoints.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from common.config import SECRET_KEY
from db.uow import TariffConsumptionUnitofWork
from model.auth import UserPublic

ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    """Decode the Bearer JWT and return the authenticated user."""
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
        if payload.get("token_type") not in (None, "access"):
            # Reject refresh tokens used as access tokens
            raise credentials_error
    except JWTError:
        raise credentials_error

    with TariffConsumptionUnitofWork() as uow:
        user = uow.user_repository.get_by_username(username)
        if user is None or not user.is_active:
            raise credentials_error
        return UserPublic(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        )
