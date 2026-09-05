"""
Canonical Schema Definition for Dark Knight Platform.

Unifies Schema A (backend/models.py SQLAlchemy models) and
Schema B (backend/data/schemas.py Pydantic models) into three core buckets:
1. Things (CanonicalEntity + EntityType)
2. Connections (CanonicalTransaction)
3. Events (CanonicalObservation)

Also includes spatial reference data models (BoundingBox, CanonicalRegion, CanonicalDetailedLocation)
and SQLAlchemy ORM persistence classes for SQLite / PostgreSQL database storage.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

from database import Base


# ---------------------------------------------------------------------------
# 1. Enums & Core Types
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    """
    Extensible Enum representing categories of 'Things'.
    Can be dynamically extended by AI ingestion or schema additions.
    """
    SUSPECT = "suspect"
    WALLET = "wallet"
    MARKET = "market"
    LISTING = "listing"
    CHANNEL = "channel"
    ACCOUNT = "account"
    IP_NODE = "ip_node"
    ORGANIZATION = "organization"

    @classmethod
    def _missing_(cls, value: object) -> EntityType:
        """Dynamically handle new/unknown entity types as string Enum values."""
        if isinstance(value, str):
            value_clean = value.lower().strip().replace(" ", "_")
            # Create dynamic enum member
            pseudo_member = str.__new__(cls, value_clean)
            pseudo_member._name_ = value_clean.upper()
            pseudo_member._value_ = value_clean
            return pseudo_member
        return super()._missing_(value)


# ---------------------------------------------------------------------------
# 2. Pydantic DTO Schemas
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    """Geographic bounding box for spatial regions."""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


class CanonicalRegion(BaseModel):
    """Spatial region definition."""
    id: str
    name: str
    lat: float
    lon: float
    bounding_box: Optional[BoundingBox] = None


class CanonicalDetailedLocation(BaseModel):
    """Specific location point belonging to a region."""
    id: str
    region_id: str
    name: str
    lat: float
    lon: float
    bounding_box: Optional[BoundingBox] = None


class CanonicalEntity(BaseModel):
    """
    Core 'Thing' concept generalization.
    Maps Suspect, CryptoWallet, DarknetListing, TelegramChannel, Market, Account, IP Node.
    """
    id: str
    type: EntityType
    identifier: str  # Uniqueness constraint across entities (e.g., wallet address, handle, URL)
    display_name: Optional[str] = None
    platform: Optional[str] = None
    location: Optional[str] = None
    risk_score: int = 0  # Justified by Suspect.risk_score (0-100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None  # Justified by Suspect.updated_at
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class CanonicalTransaction(BaseModel):
    """
    Core 'Connection' / Relationship concept generalization.
    Maps CryptoTransaction and graph edges between entities.
    """
    id: str
    tx_hash: Optional[str] = None  # Justified by CryptoTransaction.tx_hash
    source_entity_id: str
    target_entity_id: str
    amount: float = 0.0
    amount_str: Optional[str] = "UNSPECIFIED"  # Justified by CryptoTransaction.amount (string format)
    currency: str = "BTC"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class CanonicalObservation(BaseModel):
    """
    Core 'Event' concept generalization.
    Maps TelegramMessage, NetworkTrafficFlow, location sightings, and log events.
    `activity_type` is a free string for infinite extensibility.
    """
    id: str
    entity_id: str  # FK binding event to a CanonicalEntity
    source: str     # Originating platform/sensor (e.g. 'Telegram', 'NetworkFlow', 'LeafletGIS')
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region: Optional[str] = None
    activity_type: str = "general_observation"  # Free string (e.g. 'telegram_message', 'network_flow')
    risk_signal: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 3. SQLAlchemy ORM Persistence Models
# ---------------------------------------------------------------------------

class EntityModel(Base):
    """ORM table for Canonical Entities."""
    __tablename__ = "canonical_entities"

    id = Column(String(128), primary_key=True)
    type = Column(String(64), nullable=False, index=True)
    identifier = Column(String(512), nullable=False, unique=True, index=True)
    display_name = Column(String(512), nullable=True)
    platform = Column(String(128), nullable=True, index=True)
    location = Column(String(512), nullable=True)
    risk_score = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)


class TransactionModel(Base):
    """ORM table for Canonical Transactions / Graph Edges."""
    __tablename__ = "canonical_transactions"

    id = Column(String(128), primary_key=True)
    tx_hash = Column(String(128), nullable=True, index=True)
    source_entity_id = Column(String(128), nullable=False, index=True)
    target_entity_id = Column(String(128), nullable=False, index=True)
    amount = Column(Float, default=0.0, nullable=False)
    amount_str = Column(String(128), default="UNSPECIFIED", nullable=True)
    currency = Column(String(32), default="BTC", nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    metadata_json = Column(JSON, default=dict, nullable=False)


class ObservationModel(Base):
    """ORM table for Canonical Event Observations."""
    __tablename__ = "canonical_observations"

    id = Column(String(128), primary_key=True)
    entity_id = Column(String(128), nullable=False, index=True)
    source = Column(String(128), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    region = Column(String(128), nullable=True, index=True)
    activity_type = Column(String(128), nullable=False, index=True)
    risk_signal = Column(String(256), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)


class RegionModel(Base):
    """ORM table for Geographic Regions."""
    __tablename__ = "canonical_regions"

    id = Column(String(128), primary_key=True)
    name = Column(String(256), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    bounding_box_json = Column(JSON, nullable=True)


class DetailedLocationModel(Base):
    """ORM table for Detailed Location Hotspots."""
    __tablename__ = "canonical_detailed_locations"

    id = Column(String(128), primary_key=True)
    region_id = Column(String(128), ForeignKey("canonical_regions.id"), nullable=False)
    name = Column(String(256), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    bounding_box_json = Column(JSON, nullable=True)


# ---------------------------------------------------------------------------
# 4. Manifest Tables for Autonomous Resumable Background Ingestion
# ---------------------------------------------------------------------------

class IngestionFileManifestModel(Base):
    """Tracks status of ingested files across process restarts."""
    __tablename__ = "ingestion_file_manifest"

    file_path = Column(String(1024), primary_key=True)
    content_hash = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="not_started", index=True)  # not_started, in_progress, completed, failed
    total_records = Column(Integer, default=0, nullable=False)
    processed_records = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class IngestionRecordManifestModel(Base):
    """Per-record tracking within a file to guarantee process kill / crash resumability."""
    __tablename__ = "ingestion_record_manifest"

    id = Column(String(256), primary_key=True)  # file_path + ":" + record_key
    file_path = Column(String(1024), ForeignKey("ingestion_file_manifest.file_path"), nullable=False, index=True)
    record_hash = Column(String(64), nullable=False, index=True)
    canonical_record_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="pending", index=True)  # pending, mapped, new_category_created, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_file_record_status", "file_path", "status"),
    )
