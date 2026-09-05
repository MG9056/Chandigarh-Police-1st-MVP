import asyncio
from datetime import datetime, timezone
import logging
import os
from typing import Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MIN_CRAWL_DELAY_SECONDS = float(os.environ.get("MIN_CRAWL_DELAY_SECONDS", "0.5"))


class RateLimiter:
    """
    Enforces per-domain crawl delay to prevent aggressive target hammering.
    Enforces a hard floor in code (MIN_CRAWL_DELAY_SECONDS = 0.5s).
    """

    def __init__(self, default_delay: float = 1.0):
        self.default_delay = default_delay
        self.last_fetch_times: Dict[str, datetime] = {}

    def get_effective_delay(self, requested_delay: float | None) -> float:
        if requested_delay is None:
            delay = self.default_delay
        else:
            delay = float(requested_delay)

        # Enforce hard floor — cannot be configured below MIN_CRAWL_DELAY_SECONDS
        return max(delay, MIN_CRAWL_DELAY_SECONDS)

    async def wait_if_needed(self, url: str, requested_delay: float | None = None):
        domain = urlparse(url).netloc
        if not domain:
            return

        effective_delay = self.get_effective_delay(requested_delay)
        now = datetime.now(timezone.utc)

        if domain in self.last_fetch_times:
            elapsed = (now - self.last_fetch_times[domain]).total_seconds()
            if elapsed < effective_delay:
                sleep_time = effective_delay - elapsed
                logger.debug(f"Rate limiting domain {domain}: sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

        self.last_fetch_times[domain] = datetime.now(timezone.utc)
