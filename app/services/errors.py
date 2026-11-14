"""Domain errors for billing/history modules. No HTTP knowledge here."""


class DashboardDomainError(Exception):
    """Base error for dashboard requests."""

    def __init__(self, message: str):
        """Initialize the error with a message."""
        super().__init__(message)
        self.message = message


class InvalidFilterError(DashboardDomainError):
    """The supplied dashboard filters are invalid."""


class HouseholdNotFoundError(DashboardDomainError):
    """The requested household does not exist."""


class BillingPeriodNotFoundError(DashboardDomainError):
    """The requested billing period does not exist."""


class BillingPeriodOwnershipError(DashboardDomainError):
    """The billing period does not belong to the household."""
