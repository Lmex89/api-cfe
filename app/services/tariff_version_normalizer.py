"""Historical data normalization for tariff versions.

This module is kept for compatibility. Since tariff versions now use
explicit year/month keys instead of date ranges, there is no historical
date normalization to apply.
"""


def normalize_tariff_versions_history(uow) -> int:
    return 0
