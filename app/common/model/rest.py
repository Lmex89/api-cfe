from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel

from model.dashboard_serializers import BillingPeriodCostResponse
from model.domain.billing_period_model import BillingPeriod


class ValidationErrorModel(BaseModel):
    message: str
    status: Optional[int] = 422
    details: str


@dataclass(frozen=True)
class ResolvedMeterReadingQuery:
    start_date: date
    end_date: date
    billing_period: Optional[BillingPeriod] = None


@dataclass(frozen=True)
class IntervalDetails:
    consumption_since_last: Optional[float]
    days_since_last: Optional[int]
    average_daily_consumption: Optional[float]
    billing_period_cost: Optional[BillingPeriodCostResponse]
    consumption_for_total: float