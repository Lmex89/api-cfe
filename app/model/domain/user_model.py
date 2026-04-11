from datetime import datetime


class User:
    def __init__(
        self,
        username: str,
        hashed_password: str,
        role: str = "user",
        email: str | None = None,
        full_name: str | None = None,
        is_active: bool = True,
        id: int | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.hashed_password = hashed_password
        self.role = role
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at
