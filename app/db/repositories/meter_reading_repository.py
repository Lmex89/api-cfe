from datetime import date
from typing import Any, List, Optional

from common.db.base import BaseRepository
from model.domain.meter_reading_model import MeterReading


class MeterReadingRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(MeterReading).filter_by(id=id).first()

    def add(self, base_model):
        self.session.add(base_model)

    def list(
        self,
        household_id: Optional[int] = None,
        reading_date_from: Optional[date] = None,
        reading_date_to: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MeterReading]:
        query = self.session.query(MeterReading)

        if household_id is not None:
            query = query.filter(MeterReading.household_id == household_id)
        if reading_date_from is not None:
            query = query.filter(MeterReading.reading_date >= reading_date_from)
        if reading_date_to is not None:
            query = query.filter(MeterReading.reading_date <= reading_date_to)

        return (
            query.order_by(MeterReading.reading_date.asc(), MeterReading.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_household_and_date(
        self, household_id: int, reading_date: date
    ) -> Optional[MeterReading]:
        return (
            self.session.query(MeterReading)
            .filter_by(household_id=household_id, reading_date=reading_date)
            .first()
        )

    def delete(self, meter_reading: MeterReading) -> None:
        self.session.delete(meter_reading)