"""Lazy construction of the default database session factory."""

import os
from threading import Lock
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_lock = Lock()
_factory = None


def create_session_factory(url: str, isolation_level: str | None = None) -> Any:
    """Build a session factory with the requested runtime's isolation policy."""
    options: dict[str, Any] = {"pool_pre_ping": True}
    if isolation_level is not None:
        options["isolation_level"] = isolation_level
    engine = create_engine(url, **options)
    return sessionmaker(bind=engine, expire_on_commit=False)


def default_session_factory() -> Any:
    """Return the process-wide production session factory."""
    global _factory
    with _lock:
        if _factory is None:
            user = os.getenv("DB_USER")
            password = os.getenv("DB_PSWD")
            host = os.getenv("DB_HOST")
            port = os.getenv("DB_PORT")
            database = os.getenv("DB_NAME")
            url = f"mysql+mysqldb://{user}:{password}@{host}:{port}/{database}"
            _factory = create_session_factory(url, isolation_level="REPEATABLE READ")
        return _factory
