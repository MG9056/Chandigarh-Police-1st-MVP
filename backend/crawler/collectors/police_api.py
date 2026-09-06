import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .base import BaseCollector

logger = logging.getLogger(__name__)


class PoliceAPICollector(BaseCollector):
    """
    Collector for a police API that returns a JSON list.

    Expected source config:

    {
        "url": "https://example.com/api/incidents",
        "method": "GET"
    }

    Each item in the JSON list is converted into a standard
    Dark Knight crawler record.
    """

    async def fetch(
        self,
        source_config: dict,
        transport: Any,
    ) -> List[Dict[str, Any]]:

        api_url = source_config.get("url")

        if not api_url:
            logger.error("Police API source is missing a URL.")
            return []

        method = source_config.get("method", "GET").upper()

        if method != "GET":
            logger.error(
                f"Unsupported Police API method: {method}. "
                "Only GET is supported."
            )
            return []

        try:
            response = await transport.get(api_url)

            status_code = response.get("status_code")

            if status_code != 200:
                logger.warning(
                    f"Police API request to {api_url} "
                    f"returned status {status_code}"
                )
                return []

            raw_text = response.get("text", "")

            if not raw_text:
                logger.warning(
                    f"Police API returned an empty response: {api_url}"
                )
                return []

            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                logger.warning(
                    f"Police API returned invalid JSON: {api_url}"
                )
                return []

            # MVP expects the API response itself to be a list.
            if not isinstance(data, list):
                logger.warning(
                    f"Police API response must be a JSON list: {api_url}"
                )
                return []

            fetched_at = datetime.now(timezone.utc)
            records = []

            for index, item in enumerate(data):

                if isinstance(item, dict):
                    item_text = json.dumps(
                        item,
                        ensure_ascii=False,
                        indent=2,
                    )
                else:
                    item_text = str(item)

                records.append({
                    "url": f"{api_url}#record-{index}",
                    "fetched_at": fetched_at,
                    "raw_text": item_text,
                    "source": "police_api",
                })

            logger.info(
                f"Police API collector fetched {len(records)} "
                f"records from {api_url}"
            )

            return records

        except Exception as e:
            logger.error(
                f"Error fetching Police API {api_url}: {e}",
                exc_info=True,
            )
            return []