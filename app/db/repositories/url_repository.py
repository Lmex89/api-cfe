from operator import imod
from typing import Any, Optional, List
from sqlalchemy.sql.expression import false, true
from sqlalchemy.sql import select, and_
from datetime import datetime

from common.db.base import BaseRepository
from model.domain.url_model import UrlModel


class UrlRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(UrlModel).filter_by(id=id).first()

    def get_by_short_code(self, short_code: str) -> Optional[UrlModel]:
        return (
            self.session.query(UrlModel)
            .filter(UrlModel.short_code == short_code, UrlModel.active == 1)
            .first()
        )

    def get_all_url_expired(self) -> List[UrlModel]:
        return (
            self.session.query(UrlModel)
            .filter(UrlModel.active == 1, UrlModel.expires_at < datetime.now())
            .all()
        )


    def add(self, base_model):
        self.session.add(base_model)
