from datetime import datetime, timedelta

from fastapi import HTTPException
from loguru import logger
from starlette.status import HTTP_404_NOT_FOUND, HTTP_400_BAD_REQUEST

from db.url_uow import UrlShortenerUnitofWork
from model.domain.url_model import UrlModel
from model.serializers import URL, ShortURLResponse, URLCreate, URLDelete
from services.classes.short_code.expiration_service import ExpirationService
from services.classes.short_code.short_code_generator import ShortCodeGenerator
from services.classes.short_code.unique_generator import DatabaseUniquenessChecker
from services.constants import HOST_URL, TIME_EXPIRATION_URL


def expiration_checker() -> bool:
    # 1. Create an expiration service instance.
    expiration_checker = ExpirationService()
    return expiration_checker.is_expired()


def generate_unique_short_code(
    generator: ShortCodeGenerator, checker: DatabaseUniquenessChecker
) -> str:
    """
    Generates a unique short code by orchestrating a generator and a uniqueness checker.
    """
    while True:
        short_code = generator.generate()
        if checker.is_unique(short_code):
            return short_code


def get_short_code(code: str) -> str:
    return HOST_URL + code


def create_short_url(
    url: URLCreate, expiration_time_days: int = TIME_EXPIRATION_URL
) -> ShortURLResponse:
    """Creates a new entry in the database for the shortened URL."""
    logger.debug(f"Getting url from {url}")

    # Set expiration time to 30 days from now

    code_generator = ShortCodeGenerator(length=7)
    with UrlShortenerUnitofWork() as uow:
        uniqueness_checker = DatabaseUniquenessChecker(uow=uow)
        short_code = generate_unique_short_code(
            generator=code_generator, checker=uniqueness_checker
        )
        logger.debug(f"creating urlshort from {short_code}")

        db_url = UrlModel(
            short_code=short_code,
            original_url=str(url.original_url),
            expires_at=datetime.now(),
            visits=0,
        )
        db_url.set_experition_at(days=expiration_time_days)
        logger.debug(f"Creating data in Db {db_url}")
        logger.debug(f"url {short_code} expires at expires_at from {db_url.expires_at}")
        repsonse = ShortURLResponse(short_url=get_short_code(code=short_code))
        uow.url_shotner_repository.add(db_url)
        uow.commit()
        logger.debug(f"Record inserted with ID: {db_url.id} sucess")
        logger.debug(f"Creating response serialized {repsonse}")
        return repsonse


def get_original_url_by_short_code(short_code: str) -> URL | None:
    """Retrieves the URL entry based on the short code."""

    with UrlShortenerUnitofWork() as uow:
        db_url = uow.url_shotner_repository.get_by_short_code(short_code=short_code)
        logger.debug(f"Getting url from {db_url}")

        if not db_url:
            # 2. Raise a 404 error if the short code is not found
            logger.warning(f"No se encontro url related to {short_code}")
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND, detail="Short URL not found"
            )

        # 3. Check if the URL has expired
        if db_url.expires_at and db_url.expires_at < datetime.now():
            logger.error(f"Short URL has expired {short_code}")
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST, detail="Short URL has expired"
            )

        db_url.visits += 1
        logger.debug(f"Adding vists +1 url from {db_url}")
        uow.url_shotner_repository.add(db_url)
        uow.commit()

        response = URL.model_construct(**db_url.dump())
        logger.debug(f"response URL  from {response}")
        return response


def delete_expired_ulrs():
    with UrlShortenerUnitofWork() as uow:
        urls_db = uow.url_shotner_repository.get_all_url_expired()
        count = len(urls_db)
        logger.debug(f"getting urls for delete count {count}")
        for url in urls_db:
            url.set_active_(active=False)
            logger.debug(f"setting url for delete {url}")
        uow.commit()
        logger.success(f"setting url for delete {count}")
        return URLDelete(count_items_deleted=count)
