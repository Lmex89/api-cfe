from typing import Union
from fastapi.encoders import jsonable_encoder

from fastapi.exceptions import RequestValidationError
from fastapi.openapi.constants import REF_PREFIX
from fastapi.openapi.utils import validation_error_response_definition
from pydantic import ValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from common.model.rest import ValidationErrorModel

async def http422_error_handler(
    _: Request, exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:

    response = ValidationErrorModel(
        message = "Error en la validación de la petición",
        status = HTTP_422_UNPROCESSABLE_ENTITY,
        details = str(exc)
    )
    return JSONResponse(jsonable_encoder(response), status_code=HTTP_422_UNPROCESSABLE_ENTITY
    )

validation_error_response_definition["properties"] = {
    "errors": {
        "title": "Errors",
        "type": "array",
        "items": {"$ref": "{0}ValidationError".format(REF_PREFIX)},
    }
}
