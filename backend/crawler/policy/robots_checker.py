from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse
import urllib.robotparser
from sqlalchemy.orm import Session
import httpx

from crawler.models.robots_cache import RobotsCache

logger = logging.getLogger(__name__)


class RobotsChecker:
    """
    Fetches, parses, and caches robots.txt rules per domain in DB with configurable TTL.
    Prevents unauthorized path crawling.
    """

    def __init__(self, ttl_hours: int = 24):
        self.ttl_hours = ttl_hours

    async def is_allowed(self, url: str, user_agent: str, db: Session, transport: object = None) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            return True  # If no netloc/domain parsed, permit or skip

        # Check DB cache
        now = datetime.utcnow()
        cache_entry = db.query(RobotsCache).filter(RobotsCache.domain == domain).first()

        if cache_entry and (now - cache_entry.checked_at) < timedelta(hours=cache_entry.ttl_hours):
            # Use cached robots.txt summary rules
            summary = cache_entry.allowed_paths_summary or {}
            disallowed_patterns = summary.get("disallowed", [])
            for pattern in disallowed_patterns:
                if pattern and parsed.path.startswith(pattern):
                    logger.info(f"Skipping {url}: matched cached robots.txt disallowed rule {pattern}")
                    return False
            return True

        # Fetch fresh robots.txt
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)

        disallowed_paths = []
        try:
            if transport and hasattr(transport, "get"):
                res = await transport.get(robots_url)
                if res.get("status_code") == 200:
                    rp.parse(res.get("text", "").splitlines())
                else:
                    # Non-200 means default allow
                    rp.parse([])
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(robots_url)
                    if res.status_code == 200:
                        rp.parse(res.text.splitlines())
                    else:
                        rp.parse([])
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
            rp.parse([])

        # Extract disallow rules for fallback summary
        is_permitted = rp.can_fetch(user_agent, url)

        # Update DB cache
        try:
            if cache_entry:
                cache_entry.checked_at = now
                cache_entry.allowed_paths_summary = {"disallowed": disallowed_paths}
            else:
                cache_entry = RobotsCache(
                    domain=domain,
                    allowed_paths_summary={"disallowed": disallowed_paths},
                    checked_at=now,
                    ttl_hours=self.ttl_hours,
                )
                db.add(cache_entry)
            db.commit()
        except Exception as err:
            db.rollback()
            logger.error(f"Error caching robots.txt for {domain}: {err}")

        return is_permitted
