from typing import Any, List, Optional

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

    def list(
        self,
        tariff_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TariffVersion]:
        query = self.session.query(TariffVersion)
        if tariff_id is not None:
            query = query.filter(TariffVersion.tariff_id == tariff_id)
        return (
            query.order_by(
                TariffVersion.year.asc(),
                TariffVersion.month.asc(),
                TariffVersion.id.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_tariff_and_period(
        self, tariff_id: int, year: int, month: int
    ) -> Optional[TariffVersion]:
        return (
            self.session.query(TariffVersion)
            .filter_by(tariff_id=tariff_id, year=year, month=month)
            .first()
        )

    def delete(self, tariff_version: TariffVersion) -> None:
        self.session.delete(tariff_version)
