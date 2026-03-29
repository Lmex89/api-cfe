from common.db.abstract_unit_of_work import AbstractUnitOfWork
from db.database import DEFAULT_SESSION_FACTORY
from db.repositories.billing_period_repository import BillingPeriodRepository
from db.repositories.household_repository import HouseholdRepository
from db.repositories.household_tariff_repository import HouseholdTariffRepository
from db.repositories.meter_reading_repository import MeterReadingRepository
from db.repositories.tariff_range_repository import TariffRangeRepository
from db.repositories.tariff_repository import TariffRepository
from db.repositories.tariff_version_repository import TariffVersionRepository
from db.repositories.url_repository import UrlRepository



################################################################################
### Esta clase funciona como un agregado (agreggate) que se encarga de 
### manejar un conjunto de repositorios. Siempre se debe de acceder a los
### repositorios por medio de un agregado, aunque solo sea uno
################################################################################
class TariffConsumptionUnitofWork(AbstractUnitOfWork):

    def __enter__(self, session_factory=DEFAULT_SESSION_FACTORY):
        self.session = session_factory(expire_on_commit=False)
        self.url_shotner_repository = UrlRepository(self.session)
        self.household_repository = HouseholdRepository(self.session)
        self.household_tariff_repository = HouseholdTariffRepository(self.session)
        self.tariff_repository = TariffRepository(self.session)
        self.meter_reading_repository = MeterReadingRepository(self.session)
        self.billing_period_repository = BillingPeriodRepository(self.session)
        self.tariff_range_repository = TariffRangeRepository(self.session)
        self.tariff_version_repository = TariffVersionRepository(self.session)
        return self

    def __exit__(self, *args):
        super().__exit__(*args)
        self.session.close()  #(3)

    def commit(self):  #(4)
        self.session.commit()

    def rollback(self):  #(4)
        self.session.rollback()


