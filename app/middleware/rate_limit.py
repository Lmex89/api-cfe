"""
Rate limiting middleware for authentication endpoints.
"""
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


class RateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = defaultdict(list)
    
    def check_rate_limit(self, key: str) -> bool:
        now = datetime.now()
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        self.requests[key].append(now)
        return True


# Global rate limiters
auth_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)