from typing import List
from .base import BaseCollector, DemoModeEnforcedError


class TorStubCollector(BaseCollector):
    """
    Architecture stub for darknet .onion crawlers.
    Strictly raises DemoModeEnforcedError when invoked per PRD Critical Constraint #5.
    """

    async def fetch(self, source_config: dict, transport: object) -> List[dict]:
        raise DemoModeEnforcedError("Tor collector is disabled in demo mode. No live .onion requests permitted.")
