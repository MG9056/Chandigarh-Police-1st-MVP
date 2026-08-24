from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
 
from pydantic import BaseModel, Field

class EntityType(str,Enum):
    suspect="suspect"
    wallet="wallet"
    market="market"
    account="account"

class Entity(BaseModel):
    id: str
    type: EntityType
    identifier: str
    platform: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime

class Observation(BaseModel):
    id: str
    entity_id: str
    source: str
    timestamp: datetime
 
    # Location is intentionally permissive: not every observation is
    # geotagged (e.g. a forum message vs. a geolocated Tor session).
    # Cleaning/dropping unlocated observations happens later, at the point
    # where the hotspot model actually consumes this data — not here.
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region: Optional[str] = None
 
    activity_type: str
    risk_signal: Optional[str] = None
    metadata: Optional[dict] = None


class Transaction(BaseModel):
    id: str
    source_entity: str
    target_entity: str
    amount: float
    currency: str
    timestamp: datetime


class BoundingBox(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
 
 
class Region(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    bounding_box: Optional[BoundingBox] = None


class DetailedLocation(BaseModel):
    id: str
    region_id: str
    name: str
    lat: float
    lon: float
    bounding_box: Optional[BoundingBox] = None
