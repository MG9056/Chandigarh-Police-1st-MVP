"""
Canonical Schema Extensions Registry.

Auto-generated and updated by backend/pipelines/ingest_ai_router.py
when new categories or activity types are auto-classified during background ingestion.

All changes here are tracked in version control for post-ingestion review.
"""

from typing import Dict, List, Any

# Dynamic EntityType extensions auto-created by AI ingestion router
DYNAMIC_ENTITY_TYPES: Dict[str, str] = {
    # Example: "telecom_cell_tower": "Cellular Network Transceiver Entity"
}

# Dynamic Activity Types registered during observation ingestion
DYNAMIC_ACTIVITY_TYPES: Dict[str, str] = {
    "telegram_message": "Telegram messaging transmission event",
    "network_flow": "TCP/IP Network packet flow telemetry event",
    "location_ping": "GPS spatial location ping event",
    "darknet_scrape": "Marketplace listing web scrape event",
}

# Ingestion audit log for auto-created categories
AUTO_CREATED_CATEGORIES_LOG: List[Dict[str, Any]] = [
    # Records appended automatically when new categories are created
]
