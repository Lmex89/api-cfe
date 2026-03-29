from typing import Any, List, Optional

from common.db.base import BaseRepository
from model.domain.billing_period_model import BillingPeriod


class BillingPeriodRepository(BaseRepository):
    def __init__(self, session) -> None:
        super().__init__()
        self.session = session

    def get(self, id: int) -> Any:
        return self.session.query(BillingPeriod).filter_by(id=id).first()

    def add(self, base_model):
        self.session.add(base_model)

    def list(
        self,
        household_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BillingPeriod]:
        query = self.session.query(BillingPeriod)
        if household_id is not None:
            query = query.filter(BillingPeriod.household_id == household_id)
        return (
            query.order_by(BillingPeriod.start_date.asc(), BillingPeriod.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete(self, billing_period: BillingPeriod) -> None:
        self.session.delete(billing_period)
