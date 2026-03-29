from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Household:
    name: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
