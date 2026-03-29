from datetime import datetime, timezone

from services.classes.abstract.expiration_protocol import Expirable


class ExpirationService:
    """Handles the business logic for checking expiration."""

    def is_expired(self, item: Expirable) -> bool:
        """
        Checks if an item has expired.

        Returns True if the item has an expiration date that is in the past.
        Returns False if the expiration date is in the future or not set.
        """
        if item.expiration_at is None:
            # Items without an expiration date are considered not expired.
            return False

        # Compare the expiration date with the current UTC time.
        # This ensures timezone-aware comparison.
        return item.expiration_at < datetime.now(timezone.utc)


