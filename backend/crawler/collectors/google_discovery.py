from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, List
import json

from .base import BaseCollector

logger = logging.getLogger(__name__)


class GoogleDiscoveryCollector(BaseCollector):
    """
    Discovers candidate URLs via Tavily Search API.

    Formulates queries based on active case keywords.
    Tracks daily quota usage.
    """

    def __init__(self, daily_quota: int = 30):
        self.api_key = os.environ.get("TAVILY_API_KEY", "")
        self.daily_quota = int(
            os.environ.get("TAVILY_DAILY_QUOTA", daily_quota)
        )
        self.requests_used = 0

    async def fetch(
        self,
        source_config: dict,
        transport: Any
    ) -> List[Dict[str, Any]]:

        keywords = source_config.get("keywords", [])
        urls_to_fetch = source_config.get("seed_urls", [])

        if not keywords and not urls_to_fetch:
            return []

        discovered_records = []
        fetched_at = datetime.now(timezone.utc)

        # Search the web using Tavily
        if self.api_key and keywords:

            if self.requests_used >= self.daily_quota:
                logger.warning(
                    f"Tavily daily quota limit reached "
                    f"({self.requests_used}/{self.daily_quota}). "
                    f"Skipping search API call."
                )

            else:
                query_str = " ".join(keywords[:5])

                search_url = "https://api.tavily.com/search"

                payload = {
                    "api_key": self.api_key,
                    "query": query_str,
                    "search_depth": "basic",
                    "max_results": 10,
                    "include_answer": False,
                    "include_raw_content": False
                }

                try:
                    res = await transport.post(
                        search_url,
                        json=payload
                    )

                    self.requests_used += 1

                    if res.get("status_code") == 200:

                        data = json.loads(
                            res.get("text", "{}")
                        )

                        results = data.get("results", [])

                        for result in results:

                            discovered_url = result.get("url")
                            title = result.get("title", "")
                            content = result.get("content", "")

                            if discovered_url:

                                discovered_records.append({
                                    "url": discovered_url,
                                    "fetched_at": fetched_at,
                                    "raw_text": (
                                        f"<html><body>"
                                        f"<h1>{title}</h1>"
                                        f"<p>{content}</p>"
                                        f"</body></html>"
                                    ),
                                    "source": "tavily_search_discovery",
                                })

                    else:
                        logger.warning(
                            f"Tavily API returned status "
                            f"{res.get('status_code')}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error querying Tavily Search API: {e}"
                    )

        elif keywords:

            # Dev/Demo fallback when Tavily API key is not configured
            logger.info(
                "Tavily API key not set — running "
                "OSINT discovery fallback for active keywords."
            )

            for kw in keywords[:3]:

                kw_clean = kw.strip().lower()

                discovered_url = (
                    f"https://en.wikipedia.org/wiki/"
                    f"{kw_clean.capitalize()}"
                )

                try:

                    res = await transport.get(
                        discovered_url
                    )

                    if res.get("status_code") == 200:

                        discovered_records.append({
                            "url": discovered_url,
                            "fetched_at": fetched_at,
                            "raw_text": res.get("text", ""),
                            "source": "tavily_search_discovery_osint",
                        })

                except Exception as err:

                    logger.debug(
                        f"OSINT fallback fetch for "
                        f"{discovered_url} failed: {err}"
                    )

        # Fetch direct seed URLs
        for url in urls_to_fetch:

            try:

                res = await transport.get(url)

                if res.get("status_code") == 200:

                    discovered_records.append({
                        "url": url,
                        "fetched_at": fetched_at,
                        "raw_text": res.get("text", ""),
                        "source": "tavily_search_discovery_seed",
                    })

            except Exception as e:

                logger.error(
                    f"Error fetching URL {url}: {e}"
                )

        return discovered_records