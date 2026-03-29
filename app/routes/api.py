from fastapi import APIRouter

from routes import billing_periods
from routes import dashboards
from routes import households
from routes import household_tariffs
from routes import meter_readings
from routes import tariffs
from routes import tariff_ranges
from routes import tariff_versions

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(meter_readings.router)
api_router.include_router(households.router)
api_router.include_router(billing_periods.router)
api_router.include_router(household_tariffs.router)
api_router.include_router(tariffs.router)
api_router.include_router(tariff_versions.router)
api_router.include_router(tariff_ranges.router)
api_router.include_router(dashboards.router)
