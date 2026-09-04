import asyncio
from abc import ABC, abstractmethod
import os
import httpx

from .base import DemoModeEnforcedError

DEFAULT_USER_AGENT = os.environ.get(
    "DEFAULT_USER_AGENT",
    "DarkKnightCrawler/1.0 (+https://chandigarhpolice.gov.in/contact)"
)

class HTTPTransport(ABC):
    @abstractmethod
    async def get(self, url: str) -> dict:
        pass

    @abstractmethod
    async def post(self, url: str, json: dict = None, data: dict = None) -> dict:
        pass


class DirectHTTPTransport(HTTPTransport):
    """
    Direct HTTP/HTTPS transport client wrapping httpx.AsyncClient with timeout and backoff retry.
    """

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout: float = 10.0, max_retries: int = 3):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries

    async def get(self, url: str) -> dict:
        headers = {"User-Agent": self.user_agent}
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    return {
                        "status_code": resp.status_code,
                        "text": resp.text,
                        "content": resp.content,
                        "headers": dict(resp.headers),
                    }
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))  # Exponential backoff: 0.5s, 1.0s, 2.0s
                else:
                    raise last_exception

    async def post(self, url: str, json: dict = None, data: dict = None) -> dict:
        headers = {"User-Agent": self.user_agent}
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    resp = await client.post(url, headers=headers, json=json, data=data)
                    return {
                        "status_code": resp.status_code,
                        "text": resp.text,
                        "content": resp.content,
                        "headers": dict(resp.headers),
                    }
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                else:
                    raise last_exception


class TorProxyTransport(HTTPTransport):
    """
    Architecture stub for Tor SOCKS5 transport client.
    Raises DemoModeEnforcedError on all interactions per PRD Critical Constraint #5.
    """

    def __init__(self, proxy_url: str = "socks5://127.0.0.1:9050"):
        self.proxy_url = proxy_url

    async def get(self, url: str) -> dict:
        raise DemoModeEnforcedError("Tor proxy transport is disabled in demo mode.")

    async def post(self, url: str, json: dict = None, data: dict = None) -> dict:
        raise DemoModeEnforcedError("Tor proxy transport is disabled in demo mode.")

