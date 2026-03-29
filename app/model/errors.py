import json
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

HTTP_420_ENTITY_NOT_FOUND = 420


################################################################################
# Esta clase es necesaria para poder generar la documentación de OpenAPI
################################################################################
class Detail(BaseModel):
    Dato1: str
    Dato2: str
    Dato3: int


class NotFoundMessage(BaseModel):
    message: str
    data: Detail

    def toJSON(self):
        return jsonable_encoder(self)


################################################################################
# Excepción personalizada
################################################################################


class EntityNotFoundException(Exception):
    def __init__(self, description: str):
        self.description = description


async def http420_error_handler(
    _: Request, exc: EntityNotFoundException
) -> JSONResponse:
    response = NotFoundMessage(
        message=exc.description, data=Detail(Dato1="Uno", Dato2="Dos", Dato3=100)
    )

    return JSONResponse(response.toJSON(), status_code=HTTP_420_ENTITY_NOT_FOUND)
