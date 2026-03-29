from typing import Any

from common.db.base import BaseRepository
from model.domain.tariff_version_model import TariffVersion


class TariffVersionRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(TariffVersion).filter_by(id=id).first()

    def add(self, base_model):
        self.session.add(base_model)
