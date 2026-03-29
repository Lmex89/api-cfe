from pydantic import BaseModel
from typing import Dict, List, Optional

class ValidationErrorModel(BaseModel):
    message: str
    status: Optional[int] = 422
    details: str