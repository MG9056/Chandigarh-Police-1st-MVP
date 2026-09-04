from fastapi import HTTPException, status, Request
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import threading
import os

class RateLimiter:
    """
    In-memory rate limiter tracking client IP requests within rolling time windows.
    Returns HTTP 429 when thresholds are exceeded.
    """
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = threading.Lock()

    def check_rate_limit(self, request: Request, endpoint_key: str, max_requests: int, window_seconds: int = 60):
        if os.environ.get("TESTING") == "1":
            return

        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (request.client.host if request.client else "127.0.0.1")
        key = f"{endpoint_key}:{client_ip}"
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)

        with self._lock:
            # Filter timestamps outside rolling window
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]

            if len(self._requests[key]) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later."
                )

            self._requests[key].append(now)

limiter = RateLimiter()
