from typing import Any

from common.db.base import BaseRepository
from model.domain.user_model import User


class UserRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(User).filter_by(id=id).first()

    def get_by_username(self, username: str) -> User | None:
        return self.session.query(User).filter_by(username=username).first()

    def add(self, user: User) -> None:
        self.session.add(user)
