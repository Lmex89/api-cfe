"""Lazy construction of the default database session factory."""

import os
from threading import Lock
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_lock = Lock()
_factory = None


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
            engine = create_engine(
                url, isolation_level="REPEATABLE READ", pool_pre_ping=True
            )
            _factory = sessionmaker(bind=engine, expire_on_commit=False)
        return _factory
