from typing import Any, List, Optional

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

    def list(
        self,
        tariff_version_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TariffRange]:
        query = self.session.query(TariffRange)
        if tariff_version_id is not None:
            query = query.filter(TariffRange.tariff_version_id == tariff_version_id)
        return (
            query.order_by(TariffRange.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete(self, tariff_range: TariffRange) -> None:
        self.session.delete(tariff_range)
