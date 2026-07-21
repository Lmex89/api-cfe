"""
Authentication audit logging for security monitoring.
"""
import json
from datetime import datetime
from typing import Optional
from loguru import logger


def log_auth_event(event_type: str, username: Optional[str] = None, success: bool = True, details: dict = None):
    """Log authentication events for security auditing."""
    logger.info(
        json.dumps({
            "event": "auth",
            "type": event_type,
            "username": username,
            "success": success,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        })
    )