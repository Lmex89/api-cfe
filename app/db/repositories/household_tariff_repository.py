from typing import Any, List, Optional

from common.db.base import BaseRepository
from model.domain.household_tariff_model import HouseholdTariff


class HouseholdTariffRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(HouseholdTariff).filter_by(id=id).first()

    def add(self, base_model):
        self.session.add(base_model)

    def list(
        self,
        household_id: Optional[int] = None,
        tariff_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[HouseholdTariff]:
        query = self.session.query(HouseholdTariff)
        if household_id is not None:
            query = query.filter(HouseholdTariff.household_id == household_id)
        if tariff_id is not None:
            query = query.filter(HouseholdTariff.tariff_id == tariff_id)
        return (
            query.order_by(HouseholdTariff.start_date.asc(), HouseholdTariff.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete(self, household_tariff: HouseholdTariff) -> None:
        self.session.delete(household_tariff)
