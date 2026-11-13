"""Domain errors for billing/history modules. No HTTP knowledge here."""


class DashboardDomainError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidFilterError(DashboardDomainError):
    pass


class HouseholdNotFoundError(DashboardDomainError):
    pass


class BillingPeriodNotFoundError(DashboardDomainError):
    pass


class BillingPeriodOwnershipError(DashboardDomainError):
    pass
