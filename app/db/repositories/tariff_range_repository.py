from typing import Any

from common.db.base import BaseRepository
from model.domain.tariff_range_model import TariffRange


class TariffRangeRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(TariffRange).filter_by(id=id).first()

    def add(self, base_model):
        self.session.add(base_model)
