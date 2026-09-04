from typing import Dict, Type
from .base import BaseCollector
from .google_discovery import GoogleDiscoveryCollector
from .direct_seed import DirectSeedCollector
from .bitcoin import BitcoinChainCollector
from .telegram import TelegramPublicCollector
from .tor_stub import TorStubCollector


class CollectorRegistry:
    """
    Registry mapping source_type string to appropriate BaseCollector class.
    Used by orchestration scheduler to instantiate collectors per source.
    """

    _registry: Dict[str, Type[BaseCollector]] = {
        "GOOGLE_SEARCH_DISCOVERY": GoogleDiscoveryCollector,
        "DIRECT_SEED": DirectSeedCollector,
        "BITCOIN_CHAIN": BitcoinChainCollector,
        "TELEGRAM_PUBLIC": TelegramPublicCollector,
        "TOR_STUB": TorStubCollector,
    }

    @classmethod
    def register(cls, source_type: str, collector_cls: Type[BaseCollector]):
        cls._registry[source_type.upper()] = collector_cls

    @classmethod
    def get_collector_class(cls, source_type: str) -> Type[BaseCollector]:
        key = source_type.upper()
        if key not in cls._registry:
            # Fall back to DirectSeedCollector if unknown source type
            return DirectSeedCollector
        return cls._registry[key]

    @classmethod
    def get_collector(cls, source_type: str) -> BaseCollector:
        collector_cls = cls.get_collector_class(source_type)
        return collector_cls()
