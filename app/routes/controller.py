from fastapi import APIRouter, Security
from fastapi.responses import RedirectResponse
from loguru import logger
from starlette.status import HTTP_301_MOVED_PERMANENTLY

from common.api.responses import responses as HTTP_RESPONSES

################################################################################
### En app/model/rest.py se definen los modelos que servirán para comunicarse
### con el front end (tanto los que se reciben como los que se devuelven)
################################################################################
from common.services.security import APIKeyChecker
from model.serializers import ShortURLResponse, URLBase, URLCreate, URLDelete
from services import short_code_handler as handler
import os 

logger.info(f" =========== {os.getenv('CREATE_API_KEY')}")
logger.info(f" =========== {os.getenv('CREATE_API_KEY')}")

################################################################################
### Se pueden definir errores personalizados (ver la implementación en el
### archivo EntityNotFoundException)
################################################################################
router = APIRouter(responses=HTTP_RESPONSES)
require_create_key = APIKeyChecker(env_var="CREATE_API_KEY")
requere_delete_key = APIKeyChecker(env_var="DELETE_API_KEY")


################################################################################
### Se definen los parámetros que se reciben y los que se devuelven con base
### en el modelo
################################################################################
@router.post("/", response_model=ShortURLResponse)
# Solo usar async def si se requiere hacer await
def shortener(url: URLCreate,  is_authorized: bool = Security(require_create_key)) -> ShortURLResponse:
    logger.debug(f"is Autorized {is_authorized}")
    return handler.create_short_url(url=url)


@router.get("/{short_code}", response_model=URLBase)
# Solo usar async def si se requiere hacer await
def get_redirect_short_code(short_code: str) -> URLBase:
    logger.debug(f"Processing this code {short_code}")
    return RedirectResponse(
        url=handler.get_original_url_by_short_code(short_code=short_code).original_url,
        status_code=HTTP_301_MOVED_PERMANENTLY,
    )


@router.delete("/expired", response_model=URLDelete)
# Solo usar async def si se requiere hacer await
def delete_old_urls(is_authorized: bool = Security(requere_delete_key)) -> URLDelete:
    logger.debug(f"is Autorized {is_authorized}")
    response = handler.delete_expired_ulrs()
    logger.info(f"final debug -------- {response}")
    return response