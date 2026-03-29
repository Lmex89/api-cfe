from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class UrlModel:
    original_url: str
    expires_at: datetime
    short_code: str
    visits: Optional[int] = 0
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    active: int = 1

    def dump(self):
        return self.__dict__

    def __str__(self):
        return f"id={self.id}, short_code={self.short_code} original_url={self.original_url} active : {self.active}"

    def set_experition_at(self, days: int = 30) -> None:
        self.expires_at = datetime.now() + timedelta(days=days)

    def set_active_(self, active: bool):
        self.active = active
