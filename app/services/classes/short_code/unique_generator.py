from db.url_uow import UrlShortenerUnitofWork
from services.classes.abstract.uniqueness import UniquenessChecker


class DatabaseUniquenessChecker(UniquenessChecker):
    """Checks for short code uniqueness using the database."""

    def __init__(self, uow: UrlShortenerUnitofWork):
        self.uow = uow

    def is_unique(self, short_code: str) -> bool:
        """Returns True if the code does not exist in the repository."""
        return not self.uow.url_shotner_repository.get_by_short_code(
            short_code=short_code
        )
