import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from loguru import logger 
API_KEY_HEADER = APIKeyHeader(name="x-api-key", auto_error=False)


class APIKeyChecker:
    """
    A configurable dependency class to check for a specific API key.

    This class is instantiated with the name of the environment variable
    that holds the secret key. This allows for different instances to check
    for different keys.
    """

    def __init__(self, env_var: str):
        self.env_var = env_var
        self.api_key = os.getenv(self.env_var)

    async def __call__(self, api_key_header: str = Security(API_KEY_HEADER)):
        """
        The __call__ method makes instances of this class callable,
        allowing FastAPI to use them as dependencies.
        """
        if not self.api_key:
            logger.warning(f" No apikey was set {self.api_key}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Server configuration error: {self.env_var} not set.",
            )

        if api_key_header == self.api_key:
            logger.success(f"Apikey is autorized {self}")
            return True
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing API Key for this endpoint",
            )
