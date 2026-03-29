import logging
import sys
import os
from typing import List

from loguru import logger
from pydantic.main import BaseModel
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings, Secret

from common.logging import InterceptHandler

API_PREFIX = ""

JWT_TOKEN_PREFIX = "Token"

################################################################################
### Estas variables de ambiente deben existir en el ambiente en que se 
### ejecute la aplicación (no usar archivo .env)
################################################################################

DEBUG: bool = True

HOST:str = os.getenv("DB_HOST")
PORT:int = os.getenv("DB_PORT")
USER:str = os.getenv("DB_USER")
PWD:str = os.getenv("DB_PSWD")
DB:str = os.getenv("DB_NAME")

SECRET_KEY: Secret = os.getenv("SECRET_KEY")

LOGGING_LEVEL = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    handlers=[InterceptHandler(level=LOGGING_LEVEL)], level=LOGGING_LEVEL
)
logger.configure(handlers=[{"sink": sys.stderr, "level": LOGGING_LEVEL}])

ALLOWED_HOSTS: List[str] = ["*"]

class JWTSettings(BaseModel):
    authjwt_secret_key: str = SECRET_KEY

###### SERVICES #####
TWILIO_USER_NAME = os.getenv('TWILIO_USER_NAME', '')
TWILIO_USER_PWD = os.getenv('TWILIO_USER_PWD', '')
TWILIO_FROM_NUMBER = os.getenv('TWILIO_FROM_NUMBER', '')
TWILIO_PHONE_WHATSAPP = os.getenv('TWILIO_PHONE_WHATSAPP', '')

ENCRYPT_KEY = os.getenv('COMMON_ENCRYPT_KEY', '')
ENCRYPT_IMG_KEY = os.getenv('COMMON_ENCRYPT_IMG_KEY', '')

DRIVE_DIR_CREDENTIALS = '/usr/lib/python2.7/dist-packages/common/vo/credentials_module.json'
DRIVE_ID_SHARED = '0ADxzIB28mnEgUk9PVA'
DRIVE_FOLDER_SHARED = '1E1ZcsSxfynFize6njVhRn9ySGgyychQy'

###### HSM #####
HSM_HOST = os.getenv('HSM_HOST', '')
HSM_PORT = os.getenv('HSM_PORT', '')

CURRENT_DOMAIN = os.getenv('CURRENT_DOMAIN', '')