from datetime import datetime
from typing import Protocol, Optional


class Expirable(Protocol):
    """Defines the interface for any object that can expire."""

    expiration_at: Optional[datetime]
