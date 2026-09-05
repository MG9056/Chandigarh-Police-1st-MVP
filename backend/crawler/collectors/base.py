from abc import ABC, abstractmethod
from typing import Any, List


class DemoModeEnforcedError(Exception):
    """
    Raised when any code path attempts live Tor/darknet operations in demo mode.
    Enforces Critical Constraint #5 of the PRD.
    """
    pass


class BaseCollector(ABC):
    """
    Abstract Base Class for all crawler data collectors.
    Every source type implements this interface identically.
    """

    @abstractmethod
    async def fetch(self, source_config: dict, transport: Any) -> List[dict]:
        """
        Fetches raw content records given source configuration and transport.
        Returns a list of raw record dictionaries prior to evidence tagging and DB persistence.
        """
        pass
