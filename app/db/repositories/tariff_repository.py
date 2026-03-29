from typing import Any, List, Optional

from common.db.base import BaseRepository
from model.domain.tariff_model import Tariff


class TariffRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(Tariff).filter_by(id=id).first()

    def add(self, base_model):
        self.session.add(base_model)

    def list(self, limit: int = 100, offset: int = 0) -> List[Tariff]:
        return (
            self.session.query(Tariff)
            .order_by(Tariff.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_code(self, code: str) -> Optional[Tariff]:
        return self.session.query(Tariff).filter_by(code=code).first()

    def delete(self, tariff: Tariff) -> None:
        self.session.delete(tariff)
