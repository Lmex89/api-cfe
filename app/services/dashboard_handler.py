"""Compatibility wrapper for dashboard meter-reading history API."""

from datetime import date
from typing import Optional

from model.dashboard_serializers import MeterReadingHistoryDashboardResponse
from services.dashboard_service import DashboardService


_dashboard_service = DashboardService()


def get_household_meter_readings_with_history(
    household_id: int,
    billing_period_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> MeterReadingHistoryDashboardResponse:
    """Backward-compatible module API delegating to DashboardService."""
    return _dashboard_service.get_household_meter_readings_with_history(
        household_id=household_id,
        billing_period_id=billing_period_id,
        start_date=start_date,
        end_date=end_date,
    )
