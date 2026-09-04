from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from .base import BaseCollector

logger = logging.getLogger(__name__)


class TelegramPublicCollector(BaseCollector):
    """
    Public Telegram channel web collector (via t.me/s/channel_name preview pages).
    """

    async def fetch(self, source_config: dict, transport: Any) -> List[Dict[str, Any]]:
        channels = list(source_config.get("channels", []))
        seed_urls = source_config.get("seed_urls", [])

        for item in seed_urls:
            item_clean = item.strip()
            if "t.me/s/" in item_clean:
                ch = item_clean.split("t.me/s/")[-1].strip("/")
                channels.append(ch)
            elif "t.me/" in item_clean:
                ch = item_clean.split("t.me/")[-1].strip("/")
                channels.append(ch)
            elif item_clean.startswith("@"):
                channels.append(item_clean[1:])
            elif item_clean:
                channels.append(item_clean)

        # Fallback default public channel if none provided
        if not channels:
            channels = ["durov"]

        records = []
        fetched_at = datetime.now(timezone.utc)

        for channel in set(channels):
            url = f"https://t.me/s/{channel}"
            try:
                res = await transport.get(url)
                if res.get("status_code") == 200:
                    records.append({
                        "url": url,
                        "fetched_at": fetched_at,
                        "raw_text": res.get("text", ""),
                        "source": "telegram_public",
                    })
            except Exception as e:
                logger.error(f"Error fetching Telegram channel {channel}: {e}")

        return records

