from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse

async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        {
            "message":exc.detail, 
            "status": exc.status_code, 
            "details": str(jsonable_encoder(exc))
        }, 
        status_code=exc.status_code
    )
