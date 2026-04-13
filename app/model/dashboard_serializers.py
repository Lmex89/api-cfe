from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class BillingPeriodCostResponse(BaseModel):
    billing_period_id: int
    household_id: int
    household_name: str
    period_start: date
    period_end: date
    total_consumption_kwh: float
    average_daily_kwh: float
    tariff_code: str
    total_cost_witout_taxes: float
    cost_per_kwh: float
    iva: float 
    total_cost_with_iva: float
    dap: float
    total_cost: float


class ActiveTariffResponse(BaseModel):
    tariff_id: int
    code: str


class ActiveTariffVersionResponse(BaseModel):
    id: int
    tariff_id: int
    year: int
    month: int


class TariffCostCalculationResponse(BaseModel):
    total_cost: Decimal
    tariff_version: ActiveTariffVersionResponse
    dap: Decimal = Decimal("0")
    iva: Decimal = Decimal("0")


class HouseholdResponse(BaseModel):
    id: int
    name: str


class DateRangeResponse(BaseModel):
    start: date
    end: date


class MeterReadingPointResponse(BaseModel):
    date: date
    reading_kwh: float
    is_initial: bool


class HouseholdConsumptionDashboardResponse(BaseModel):
    household: HouseholdResponse
    period: DateRangeResponse
    total_consumption_kwh: float
    average_daily_kwh: float
    number_of_readings: int
    readings: List[MeterReadingPointResponse]


class MultiplePeriodsSummaryResponse(BaseModel):
    household: HouseholdResponse
    period_range: DateRangeResponse
    number_of_periods: int
    total_consumption_kwh: float
    total_cost: float
    periods: List[BillingPeriodCostResponse]


class MeterReadingWithHistoryResponse(BaseModel):
    """Single meter reading with historical consumption context."""
    id: int
    household_id: int
    reading_date: date
    reading_kwh: float
    is_initial: bool
    created_at: Optional[datetime] = None
    consumption_since_last: Optional[float] = None
    days_since_last: Optional[int] = None
    average_daily_consumption_since_last: Optional[float] = None


class MeterReadingHistoryDashboardResponse(BaseModel):
    """Dashboard response for meter readings with historical consumption."""
    household: HouseholdResponse
    billing_period: Optional[BillingPeriodInfoResponse] = None
    period: DateRangeResponse
    number_of_readings: int
    total_consumption_kwh: float
    readings: List[MeterReadingWithHistoryResponse]


class BillingPeriodInfoResponse(BaseModel):
    """Billing period information."""
    id: int
    start_date: date
    end_date: date
