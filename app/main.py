from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from common.api.errors.http_error import http_error_handler
from common.api.errors.validation_error import http422_error_handler
from model.errors import EntityNotFoundException, http420_error_handler
from routes.api import api_router
from common.config import ALLOWED_HOSTS, API_PREFIX, DEBUG
from db import orm
from db.database import init_db


def get_application() -> FastAPI:
    application = FastAPI(title="URL shortener", debug=DEBUG, version="1.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_HOSTS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_exception_handler(HTTPException, http_error_handler)
    application.add_exception_handler(RequestValidationError, http422_error_handler)
    application.add_exception_handler(EntityNotFoundException, http420_error_handler)

    application.include_router(api_router, prefix=API_PREFIX)

    return application


app = get_application()

orm.start_mappers()

