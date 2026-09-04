from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from .base import BaseCollector

logger = logging.getLogger(__name__)


class BitcoinChainCollector(BaseCollector):
    """
    Public blockchain collector for Bitcoin address / transaction data.
    """

    async def fetch(self, source_config: dict, transport: Any) -> List[Dict[str, Any]]:
        addresses = list(source_config.get("addresses", []))
        seed_urls = source_config.get("seed_urls", [])

        for item in seed_urls:
            item_clean = item.strip()
            if "blockchain.info/rawaddr/" in item_clean:
                addr = item_clean.split("rawaddr/")[-1].strip("/")
                addresses.append(addr)
            elif item_clean.startswith("1") or item_clean.startswith("3") or item_clean.startswith("bc1"):
                addresses.append(item_clean)
            elif item_clean:
                addresses.append(item_clean)

        # Fallback default public address if none provided
        if not addresses:
            addresses = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]

        records = []
        fetched_at = datetime.now(timezone.utc)

        for addr in set(addresses):
            url = f"https://blockchain.info/rawaddr/{addr}"
            try:
                res = await transport.get(url)
                if res.get("status_code") == 200:
                    records.append({
                        "url": url,
                        "fetched_at": fetched_at,
                        "raw_text": res.get("text", ""),
                        "source": "bitcoin_chain",
                    })
            except Exception as e:
                logger.error(f"Error fetching Bitcoin address {addr}: {e}")

        return records

