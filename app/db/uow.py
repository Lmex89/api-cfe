from typing import Any

from common.db.abstract_unit_of_work import AbstractUnitOfWork
from db.database import default_session_factory  # type: ignore[import-not-found]
from db.repositories.billing_period_repository import BillingPeriodRepository
from db.repositories.household_repository import HouseholdRepository
from db.repositories.household_tariff_repository import HouseholdTariffRepository
from db.repositories.meter_reading_repository import MeterReadingRepository
from db.repositories.tariff_range_repository import TariffRangeRepository
from db.repositories.tariff_repository import TariffRepository
from db.repositories.tariff_version_repository import TariffVersionRepository
from db.repositories.url_repository import UrlRepository
from db.repositories.user_repository import UserRepository



################################################################################
### Esta clase funciona como un agregado (agreggate) que se encarga de 
### manejar un conjunto de repositorios. Siempre se debe de acceder a los
### repositorios por medio de un agregado, aunque solo sea uno
################################################################################
class TariffConsumptionUnitofWork(AbstractUnitOfWork):

    def __init__(self, session_factory: Any = None) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> Any:
        """Acquire a session and bind the repositories."""
        factory = self.session_factory if self.session_factory is not None else default_session_factory()
        self.session = factory(expire_on_commit=False)
        self.url_shotner_repository = UrlRepository(self.session)
        self.household_repository = HouseholdRepository(self.session)
        self.household_tariff_repository = HouseholdTariffRepository(self.session)
        self.tariff_repository = TariffRepository(self.session)
        self.meter_reading_repository = MeterReadingRepository(self.session)
        self.billing_period_repository = BillingPeriodRepository(self.session)
        self.tariff_range_repository = TariffRangeRepository(self.session)
        self.tariff_version_repository = TariffVersionRepository(self.session)
        self.user_repository = UserRepository(self.session)
        return self

    def __exit__(self, *args):
        super().__exit__(*args)

    def commit(self):  #(4)
        self.session.commit()

    def rollback(self):  #(4)
        self.session.rollback()
