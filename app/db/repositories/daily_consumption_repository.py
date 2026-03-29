from typing import Any

from common.db.base import BaseRepository
from model.domain.daily_consumption_model import DailyConsumption


class DailyConsumptionRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(DailyConsumption).filter_by(id=id).first()

    def add(self, base_model):
        self.session.add(base_model)
