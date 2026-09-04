from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from .base import BaseCollector

logger = logging.getLogger(__name__)


class DirectSeedCollector(BaseCollector):
    """
    Fallback collector fetching a explicit seed URLs list directly via HTTP transport.
    """

    async def fetch(self, source_config: dict, transport: Any) -> List[Dict[str, Any]]:
        seed_urls = list(source_config.get("seed_urls", []))
        if not seed_urls:
            seed_urls = [
                "https://en.wikipedia.org/wiki/Heroin",
                "https://en.wikipedia.org/wiki/Fentanyl"
            ]

        records = []
        fetched_at = datetime.now(timezone.utc)

        for url in seed_urls:
            try:
                res = await transport.get(url)
                if res.get("status_code") == 200:
                    records.append({
                        "url": url,
                        "fetched_at": fetched_at,
                        "raw_text": res.get("text", ""),
                        "source": "direct_seed",
                    })
                else:
                    logger.warning(f"Direct seed fetch for {url} returned status {res.get('status_code')}")
            except Exception as e:
                logger.error(f"Error executing direct seed fetch for {url}: {e}")

        return records

