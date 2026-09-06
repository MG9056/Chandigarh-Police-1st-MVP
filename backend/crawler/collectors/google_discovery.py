from datetime import datetime, timezone, timedelta
import json
import logging
import os
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from .base import BaseCollector

logger = logging.getLogger(__name__)


class GoogleDiscoveryCollector(BaseCollector):
    """
    Recursive web discovery collector using Tavily.

    Discovery state is stored inside source_config["_discovery_state"]
    so future crawl cycles can continue from previous discoveries.

    The collector:
    1. Takes the next query from a persistent discovery queue.
    2. Searches Tavily.
    3. Stores new URLs.
    4. Generates follow-up queries from newly discovered pages/domains.
    5. Persists the updated discovery state through source_config.
    """
    DOMAIN_REVISIT_COOLDOWN_SECONDS = 60
    MAX_RESULTS_PER_DOMAIN_PER_CYCLE = 2
    MAX_QUERY_QUEUE = 50
    MAX_SEEN_QUERIES = 500
    MAX_SEEN_URLS = 2000
    MAX_SEEN_DOMAINS = 500
    URL_REVISIT_COOLDOWN_SECONDS = 60

    def __init__(self, daily_quota: int = 30):
        self.api_key = os.environ.get("TAVILY_API_KEY", "")
        self.daily_quota = int(
            os.environ.get("TAVILY_DAILY_QUOTA", daily_quota)
        )
        self.requests_used = 0

    @staticmethod
    def _normalise_query(query: str) -> str:
        return re.sub(r"\s+", " ", query.strip().lower())

    @staticmethod
    def _get_domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return ""

    @staticmethod
    def _clean_phrase(text: str, max_words: int = 8) -> str:
        """
        Extract a compact search phrase from a title/content fragment.
        """
        words = re.findall(r"[A-Za-z0-9@._'-]+", text or "")

        if not words:
            return ""

        return " ".join(words[:max_words])

    def _initial_queries(self, keywords: List[str]) -> List[str]:
        """
        Create an initial set of focused queries.

        Instead of permanently using the first five keywords, create
        several small combinations that can later be replaced/expanded
        by discovery-derived queries.
        """
        cleaned = []

        for keyword in keywords:
            keyword = keyword.strip()

            if keyword and keyword not in cleaned:
                cleaned.append(keyword)

        queries = []

        # First broad query.
        if cleaned:
            queries.append(" ".join(cleaned[:5]))

        # Additional focused queries.
        for i in range(0, min(len(cleaned), 12), 2):
            pair = cleaned[i:i + 2]

            if len(pair) >= 2:
                queries.append(" ".join(pair))

        return queries

    def _add_query(
        self,
        state: Dict[str, Any],
        query: str,
    ) -> None:
        """
        Add a query to the persistent discovery queue if it has not
        previously been searched or queued.
        """
        query = self._normalise_query(query)

        if not query:
            return

        if len(query) > 300:
            query = query[:300].strip()

        seen_queries = set(state.get("seen_queries", []))
        queue = state.setdefault("query_queue", [])

        if query in seen_queries:
            return

        if query in queue:
            return

        if len(queue) >= self.MAX_QUERY_QUEUE:
            return

        queue.append(query)

    def _generate_follow_up_queries(
        self,
        state: Dict[str, Any],
        result: Dict[str, Any],
        keywords: List[str],
    ) -> None:
        """
        Generate the next investigative search directions from a
        Tavily result.

        This is intentionally deterministic for the MVP. Later the LLM
        can generate much smarter entity/relationship-driven queries.
        """
        url = result.get("url", "")
        title = result.get("title", "")
        content = result.get("content", "")

        domain = self._get_domain(url)

        # Which active keywords appear in the current result?
        matched_keywords = []

        text = f"{title} {content}".lower()

        for keyword in keywords:
            clean_keyword = keyword.strip()

            if (
                clean_keyword
                and clean_keyword.lower() in text
                and clean_keyword.lower() not in matched_keywords
            ):
                matched_keywords.append(clean_keyword.lower())

        # Fallback to the first active keyword if none explicitly matched.
        if not matched_keywords and keywords:
            matched_keywords.append(keywords[0].strip().lower())

        # ---------------------------------------------------------
        # 1. Domain expansion
        # ---------------------------------------------------------
        #
        # Example:
        # site:example.com tramadol
        #
        # This lets the crawler explore another page on a domain that
        # was just discovered.
        #
        if domain:
            state.setdefault("seen_domains", [])

            if domain not in state["seen_domains"]:
                state["seen_domains"].append(domain)

            domain_keyword = (
                matched_keywords[0]
                if matched_keywords
                else "drug"
            )

            self._add_query(
                state,
                f"site:{domain} {domain_keyword}",
            )

        # ---------------------------------------------------------
        # 2. Title-based expansion
        # ---------------------------------------------------------
        #
        # Example:
        # "example vendor marketplace" tramadol
        #
        title_phrase = self._clean_phrase(title)

        if title_phrase and matched_keywords:
            self._add_query(
                state,
                f'"{title_phrase}" {matched_keywords[0]}',
            )

        # ---------------------------------------------------------
        # 3. Distinctive lead-word expansion
        # ---------------------------------------------------------
        #
        # This is deliberately conservative. We only generate a query
        # when the content contains a potentially useful discovery term.
        #
        lead_terms = [
            "telegram",
            "vendor",
            "seller",
            "marketplace",
            "shipment",
            "escrow",
            "bitcoin",
            "crypto",
            "wallet",
        ]

        found_leads = [
            term
            for term in lead_terms
            if term in text
        ]

        if found_leads and matched_keywords:
            lead = found_leads[0]

            self._add_query(
                state,
                f"{lead} {matched_keywords[0]}",
            )

    def _get_state(
        self,
        source_config: Dict[str, Any],
        keywords: List[str],
    ) -> Dict[str, Any]:
        """
        Initialise persistent discovery state if needed.
        """
        state = source_config.setdefault(
            "_discovery_state",
        {
            "query_queue": [],
            "seen_queries": [],
            "seen_urls": [],
            "seen_url_times": {},
            "seen_domains": [],
            "domain_last_seen": {},
            "cycles": 0,
        }
        )

        state.setdefault("query_queue", [])
        state.setdefault("seen_queries", [])
        state.setdefault("seen_urls", [])
        state.setdefault("seen_url_times", {})
        state.setdefault("seen_domains", [])
        state.setdefault("domain_last_seen", {})
        state.setdefault("cycles", 0)

        if not state["query_queue"] and not state["seen_queries"]:
            for query in self._initial_queries(keywords):
                self._add_query(state, query)

        return state

    def _trim_state(self, state: Dict[str, Any]) -> None:
        """
        Prevent discovery state from growing forever.
        """
        state["query_queue"] = state.get(
            "query_queue", []
        )[-self.MAX_QUERY_QUEUE:]

        state["seen_queries"] = state.get(
            "seen_queries", []
        )[-self.MAX_SEEN_QUERIES:]

        state["seen_urls"] = state.get(
            "seen_urls", []
        )[-self.MAX_SEEN_URLS:]

        state["seen_domains"] = state.get(
            "seen_domains", []
        )[-self.MAX_SEEN_DOMAINS:]

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

        state = self._get_state(
            source_config,
            keywords,
        )

        state["cycles"] = int(state.get("cycles", 0)) + 1

        # ---------------------------------------------------------
        # Tavily recursive discovery
        # ---------------------------------------------------------
        if self.api_key and keywords:

            if self.requests_used >= self.daily_quota:
                logger.warning(
                    f"Tavily daily quota limit reached "
                    f"({self.requests_used}/{self.daily_quota}). "
                    f"Skipping search API call."
                )
            else:
                # Pick the next unexplored query.
                query = None

                while state["query_queue"]:
                    candidate = state["query_queue"].pop(0)

                    if candidate not in state["seen_queries"]:
                        query = candidate
                        break

                # Safety fallback if the queue somehow becomes empty.
                if query is None:
                    fallback_queries = self._initial_queries(keywords)

                    for candidate in fallback_queries:
                        normalised = self._normalise_query(candidate)

                        if normalised not in state["seen_queries"]:
                            query = normalised
                            break

                if query:
                    search_url = "https://api.tavily.com/search"

                    payload = {
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 10,
                        "include_answer": False,
                        "include_raw_content": False,
                    }

                    try:
                        logger.info(
                            f"Tavily recursive discovery query: {query}"
                        )

                        res = await transport.post(
                            search_url,
                            json=payload
                        )

                        self.requests_used += 1

                        state["seen_queries"].append(query)

                        if res.get("status_code") == 200:

                            data = json.loads(
                                res.get("text", "{}")
                            )

                            results = data.get("results", [])

                            logger.info(
                                f"Tavily returned {len(results)} "
                                f"results for query: {query}"
                            )

                            domain_results_this_cycle = {}

                            for result in results:
                                discovered_url = result.get("url")

                                if not discovered_url:
                                    continue

                                domain = self._get_domain(discovered_url)

                                if not domain:
                                    continue

                                now = datetime.now(timezone.utc)

                                # ---------------------------------------------------------
                                # URL-level revisit cooldown
                                # ---------------------------------------------------------
                                last_seen_raw = state.get(
                                    "seen_url_times",
                                    {}
                                ).get(discovered_url)

                                if last_seen_raw:
                                    try:
                                        last_seen = datetime.fromisoformat(
                                            last_seen_raw
                                        )

                                        if last_seen.tzinfo is None:
                                            last_seen = last_seen.replace(
                                                tzinfo=timezone.utc
                                            )

                                        age_seconds = (
                                            now - last_seen
                                        ).total_seconds()

                                        if age_seconds < self.URL_REVISIT_COOLDOWN_SECONDS:
                                            continue

                                    except (ValueError, TypeError):
                                        pass

                                # ---------------------------------------------------------
                                # Domain-level revisit cooldown
                                # ---------------------------------------------------------
                                domain_last_seen_raw = state.get(
                                    "domain_last_seen",
                                    {}
                                ).get(domain)

                                if domain_last_seen_raw:
                                    try:
                                        domain_last_seen = datetime.fromisoformat(
                                            domain_last_seen_raw
                                        )

                                        if domain_last_seen.tzinfo is None:
                                            domain_last_seen = domain_last_seen.replace(
                                                tzinfo=timezone.utc
                                            )

                                        domain_age_seconds = (
                                            now - domain_last_seen
                                        ).total_seconds()

                                        if domain_age_seconds < self.DOMAIN_REVISIT_COOLDOWN_SECONDS:
                                            continue

                                    except (ValueError, TypeError):
                                        pass

                                # ---------------------------------------------------------
                                # Limit results from one domain in this cycle
                                # ---------------------------------------------------------
                                domain_count = domain_results_this_cycle.get(
                                    domain,
                                    0
                                )

                                if domain_count >= self.MAX_RESULTS_PER_DOMAIN_PER_CYCLE:
                                    continue

                                # ---------------------------------------------------------
                                # Accept this result
                                # ---------------------------------------------------------
                                state.setdefault(
                                    "seen_url_times",
                                    {}
                                )[discovered_url] = now.isoformat()

                                state.setdefault(
                                    "domain_last_seen",
                                    {}
                                )[domain] = now.isoformat()

                                if discovered_url not in state["seen_urls"]:
                                    state["seen_urls"].append(
                                        discovered_url
                                    )

                                if domain not in state["seen_domains"]:
                                    state["seen_domains"].append(
                                        domain
                                    )

                                domain_results_this_cycle[domain] = (
                                    domain_count + 1
                                )

                                title = result.get("title", "")
                                content = result.get("content", "")

                                discovered_record = {
                                    "url": discovered_url,
                                    "fetched_at": fetched_at,
                                    "raw_text": (
                                        f"<html><body>"
                                        f"<h1>{title}</h1>"
                                        f"<p>{content}</p>"
                                        f"</body></html>"
                                    ),
                                    "source": "tavily_recursive_discovery",
                                }

                                discovered_records.append(
                                    discovered_record
                                )

                                # Generate future discovery queries from this result.
                                self._generate_follow_up_queries(
                                    state,
                                    result,
                                    keywords,
                                )
                        else:
                            logger.warning(
                                f"Tavily API returned status "
                                f"{res.get('status_code')}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Error querying Tavily Search API: {e}",
                            exc_info=True,
                        )

        elif keywords:
            # Keep the existing development fallback.
            logger.info(
                "Tavily API key not set — running "
                "OSINT discovery fallback for active keywords."
            )

            fallback_keywords = keywords[:3]

            for kw in fallback_keywords:

                kw_clean = kw.strip().lower()

                discovered_url = (
                    f"https://en.wikipedia.org/wiki/"
                    f"{kw_clean.capitalize()}"
                )

                if discovered_url in state["seen_urls"]:
                    continue

                try:
                    res = await transport.get(
                        discovered_url
                    )

                    if res.get("status_code") == 200:

                        state["seen_urls"].append(
                            discovered_url
                        )

                        discovered_records.append({
                            "url": discovered_url,
                            "fetched_at": fetched_at,
                            "raw_text": res.get("text", ""),
                            "source": (
                                "tavily_search_discovery_osint"
                            ),
                        })

                except Exception as err:

                    logger.debug(
                        f"OSINT fallback fetch for "
                        f"{discovered_url} failed: {err}"
                    )

        # ---------------------------------------------------------
        # Direct seed URLs
        # ---------------------------------------------------------
        #
        # Preserve the existing seed URL support.
        #
        for url in urls_to_fetch:

            now = datetime.now(timezone.utc)

            last_seen_raw = state.get(
                "seen_url_times",
                {}
            ).get(url)

            if last_seen_raw:
                try:
                    last_seen = datetime.fromisoformat(
                        last_seen_raw
                    )

                    if last_seen.tzinfo is None:
                        last_seen = last_seen.replace(
                            tzinfo=timezone.utc
                        )

                    age_seconds = (
                        now - last_seen
                    ).total_seconds()

                    if age_seconds < self.URL_REVISIT_COOLDOWN_SECONDS:
                        continue

                except (ValueError, TypeError):
                    pass

            try:

                res = await transport.get(url)

                if res.get("status_code") == 200:

                    state["seen_url_times"][url] = (
                        now.isoformat()
                    )

                    if url not in state["seen_urls"]:
                        state["seen_urls"].append(url)

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

        self._trim_state(state)

        logger.info(
            "Discovery state: "
            f"cycle={state['cycles']} "
            f"queue={len(state['query_queue'])} "
            f"seen_queries={len(state['seen_queries'])} "
            f"seen_urls={len(state['seen_urls'])}"
        )

        return discovered_records