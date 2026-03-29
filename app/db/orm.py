from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import registry

from model.domain.billing_period_model import BillingPeriod
from model.domain.daily_consumption_model import DailyConsumption
from model.domain.household_model import Household
from model.domain.household_tariff_model import HouseholdTariff
from model.domain.tariff_model import Tariff
from model.domain.tariff_range_model import TariffRange
from model.domain.tariff_version_model import TariffVersion
from model.domain.url_model import UrlModel

# Create a registry instance
mapper_registry = registry()


metadata = MetaData()
################################################################################
### Se debe de realizar el mapeo entre clases de negocio y la base de datos
### el mapeo se hace del modo "tradicional" de SQLAlquemy
################################################################################
households_table = Table(
    "households",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=True),
    Column("tariff_code", String(10), nullable=False),
    Column("created_at", DateTime, nullable=True, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=True,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    ),
)

tariffs_table = Table(
    "tariffs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(10), nullable=False, unique=True),
    Column("description", String(255), nullable=True),
    Column("created_at", DateTime, nullable=True, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=True,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    ),
)

billing_periods_table = Table(
    "billing_periods",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("household_id", BigInteger, ForeignKey("households.id"), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column("created_at", DateTime, nullable=True, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=True,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    ),
    Index("idx_household_period", "household_id", "start_date", "end_date"),
)

daily_consumption_table = Table(
    "daily_consumption",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("household_id", BigInteger, ForeignKey("households.id"), nullable=False),
    Column("consumption_date", Date, nullable=False),
    Column("kwh", Numeric(10, 3), nullable=False),
    Column("created_at", DateTime, nullable=True, server_default=func.current_timestamp()),
    UniqueConstraint("household_id", "consumption_date", name="uniq_household_date"),
    Index("idx_household_date", "household_id", "consumption_date"),
)

tariff_versions_table = Table(
    "tariff_versions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tariff_id", Integer, ForeignKey("tariffs.id"), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=True),
    Column("created_at", DateTime, nullable=True, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=True,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    ),
    UniqueConstraint("tariff_id", "start_date", name="uniq_tariff_period"),
)

tariff_ranges_table = Table(
    "tariff_ranges",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tariff_version_id", Integer, ForeignKey("tariff_versions.id"), nullable=False),
    Column("range_min", Numeric(10, 2), nullable=False),
    Column("range_max", Numeric(10, 2), nullable=True),
    Column("price_per_kwh", Numeric(10, 5), nullable=False),
    Column("created_at", DateTime, nullable=True, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=True,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    ),
    Index("idx_tariff_version", "tariff_version_id"),
)

household_tariffs_table = Table(
    "household_tariffs",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("household_id", BigInteger, ForeignKey("households.id"), nullable=False),
    Column("tariff_id", Integer, ForeignKey("tariffs.id"), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=True),
    Column("created_at", DateTime, nullable=True, server_default=func.current_timestamp()),
    Column(
        "updated_at",
        DateTime,
        nullable=True,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
    ),
    Index("fk_ht_tariff", "tariff_id"),
    Index("idx_ht_lookup", "household_id", "start_date", "end_date"),
)

urls_table = Table(
    "urls",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("short_code", String(10), nullable=False, unique=True, index=True),
    Column("original_url", Text, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("expires_at", DateTime, nullable=True),
    Column("visits", Integer, nullable=False, server_default="0"),
    Column("active", Integer, nullable=False, server_default="1"),
)


################################################################################
### Este método se llama al inicio del programa, no se debe de cambiar el
### nombre de la función y debe de contener todos los mapeos
################################################################################
def start_mappers():
    mapper_registry.map_imperatively(
        Household,
        households_table,
        properties={
            "id": households_table.c.id,
            "name": households_table.c.name,
            "tariff_code": households_table.c.tariff_code,
            "created_at": households_table.c.created_at,
            "updated_at": households_table.c.updated_at,
        },
    )

    mapper_registry.map_imperatively(
        Tariff,
        tariffs_table,
        properties={
            "id": tariffs_table.c.id,
            "code": tariffs_table.c.code,
            "description": tariffs_table.c.description,
            "created_at": tariffs_table.c.created_at,
            "updated_at": tariffs_table.c.updated_at,
        },
    )

    mapper_registry.map_imperatively(
        BillingPeriod,
        billing_periods_table,
        properties={
            "id": billing_periods_table.c.id,
            "household_id": billing_periods_table.c.household_id,
            "start_date": billing_periods_table.c.start_date,
            "end_date": billing_periods_table.c.end_date,
            "created_at": billing_periods_table.c.created_at,
            "updated_at": billing_periods_table.c.updated_at,
        },
    )

    mapper_registry.map_imperatively(
        DailyConsumption,
        daily_consumption_table,
        properties={
            "id": daily_consumption_table.c.id,
            "household_id": daily_consumption_table.c.household_id,
            "consumption_date": daily_consumption_table.c.consumption_date,
            "kwh": daily_consumption_table.c.kwh,
            "created_at": daily_consumption_table.c.created_at,
        },
    )

    mapper_registry.map_imperatively(
        TariffVersion,
        tariff_versions_table,
        properties={
            "id": tariff_versions_table.c.id,
            "tariff_id": tariff_versions_table.c.tariff_id,
            "start_date": tariff_versions_table.c.start_date,
            "end_date": tariff_versions_table.c.end_date,
            "created_at": tariff_versions_table.c.created_at,
            "updated_at": tariff_versions_table.c.updated_at,
        },
    )

    mapper_registry.map_imperatively(
        TariffRange,
        tariff_ranges_table,
        properties={
            "id": tariff_ranges_table.c.id,
            "tariff_version_id": tariff_ranges_table.c.tariff_version_id,
            "range_min": tariff_ranges_table.c.range_min,
            "range_max": tariff_ranges_table.c.range_max,
            "price_per_kwh": tariff_ranges_table.c.price_per_kwh,
            "created_at": tariff_ranges_table.c.created_at,
            "updated_at": tariff_ranges_table.c.updated_at,
        },
    )

    mapper_registry.map_imperatively(
        HouseholdTariff,
        household_tariffs_table,
        properties={
            "id": household_tariffs_table.c.id,
            "household_id": household_tariffs_table.c.household_id,
            "tariff_id": household_tariffs_table.c.tariff_id,
            "start_date": household_tariffs_table.c.start_date,
            "end_date": household_tariffs_table.c.end_date,
            "created_at": household_tariffs_table.c.created_at,
            "updated_at": household_tariffs_table.c.updated_at,
        },
    )

    mapper_registry.map_imperatively(
        UrlModel,
        urls_table,
        properties={
            "id": urls_table.c.id,
            "short_code": urls_table.c.short_code,
            "original_url": urls_table.c.original_url,
            "created_at": urls_table.c.created_at,
            "expires_at": urls_table.c.expires_at,
            "visits": urls_table.c.visits,
            "active": urls_table.c.active,
        },
    )
