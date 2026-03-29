from typing import Protocol

class UniquenessChecker(Protocol):
    """Defines the interface for checking if a code is unique."""

    def is_unique(self, short_code: str) -> bool:
        pass