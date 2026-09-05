from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base

def utc_now():
    return datetime.now(timezone.utc)

class RoleEnum:
    SUPER_ADMIN = "SUPER ADMIN / DGP"
    IGP = "IGP"
    SP = "SP"
    INSPECTOR = "INSPECTOR"
    INVESTIGATOR = "INVESTIGATOR"
    CONSTABLE = "CONSTABLE"

    @classmethod
    def hierarchy(cls):
        return [
            cls.SUPER_ADMIN,
            cls.IGP,
            cls.SP,
            cls.INSPECTOR,
            cls.INVESTIGATOR,
            cls.CONSTABLE
        ]

    @classmethod
    def get_rank(cls, role_name: str) -> int:
        hierarchy = cls.hierarchy()
        if role_name in hierarchy:
            return hierarchy.index(role_name)
        return 999  # Lowest authority for unknown role

class AccountStatusEnum:
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    badge_number = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default=RoleEnum.CONSTABLE)
    account_status = Column(String, nullable=False, default=AccountStatusEnum.PENDING)
    
    # 2FA
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String, nullable=True)
    recovery_codes_hash = Column(Text, nullable=True)  # JSON string of hashed recovery codes
    
    # Brute-force protection
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    refresh_sessions = relationship("RefreshSession", back_populates="user", cascade="all, delete-orphan")

class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    refresh_token_hash = Column(String, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, index=True, nullable=False)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    user = relationship("User", back_populates="refresh_sessions")

class InvestigationAccessGrant(Base):
    __tablename__ = "investigation_access_grants"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(String, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission = Column(String, nullable=False, default="MODIFY")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False, index=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_user_investigation", "user_id", "investigation_id"),
    )

class AuditLog(Base):
    """
    Append-only security and activity audit log.
    No application code should execute UPDATE or DELETE queries on this table.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    user_id = Column(Integer, nullable=True, index=True)
    role = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True, index=True)
    resource_id = Column(String, nullable=True)
    result = Column(String, nullable=False)  # SUCCESS, FAILURE, DENIED
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)

class DataProvenance(Base):
    """
    Intelligence data provenance metadata to retain source origin, collection method,
    integrity hash, and original record reference.
    """
    __tablename__ = "data_provenances"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, nullable=False)  # Darknet, Telegram, Blockchain, Public Forum
    source_name = Column(String, nullable=False)
    source_identifier = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    collection_method = Column(String, nullable=False, default="Authorized automated collection")
    collected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    investigation_id = Column(String, nullable=True, index=True)
    original_record_reference = Column(String, nullable=True)
    integrity_hash = Column(String, nullable=True)  # SHA-256 hash of original raw data/file

# --- Helper Functions ---

def time_step_to_timestamp(time_step: int) -> datetime:
    """
    Maps Elliptic++ discrete time_step integers (1..49) to concrete UTC datetimes.
    Formula: Base epoch (2019-01-01T00:00:00Z) + (time_step - 1) * 2 weeks.
    (Elliptic dataset timesteps represent ~2-week observation windows starting early 2019).
    """
    from datetime import timedelta
    base_epoch = datetime(2019, 1, 1, tzinfo=timezone.utc)
    step = max(1, time_step)
    return base_epoch + timedelta(weeks=2 * (step - 1))

# --- Domain & Intelligence Models for Project Dark Knight ---

class Suspect(Base):
    __tablename__ = "suspects"

    id = Column(Integer, primary_key=True, index=True)
    primary_alias = Column(String, nullable=False, index=True)
    aliases_json = Column(Text, nullable=True)          # JSON list of known handles/aliases
    pgp_fingerprint = Column(String, nullable=True, index=True)
    phone_number = Column(String, nullable=True, index=True)
    telegram_handle = Column(String, nullable=True, index=True)
    risk_score = Column(Integer, default=50, index=True) # Risk score (0-100)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    wallets = relationship("CryptoWallet", back_populates="suspect", cascade="all, delete-orphan")
    listings = relationship("DarknetListing", back_populates="suspect")


class CryptoWallet(Base):
    __tablename__ = "crypto_wallets"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, unique=True, nullable=False, index=True)
    currency = Column(String, nullable=False, default="BTC", index=True)
    balance = Column(String, nullable=True, default="0.0")
    risk_level = Column(String, nullable=False, default="UNKNOWN", index=True)
    associated_suspect_id = Column(Integer, ForeignKey("suspects.id"), nullable=True, index=True)

    suspect = relationship("Suspect", back_populates="wallets")
    outgoing_txs = relationship("CryptoTransaction", foreign_keys="[CryptoTransaction.from_address]", primaryjoin="CryptoWallet.address==CryptoTransaction.from_address")
    incoming_txs = relationship("CryptoTransaction", foreign_keys="[CryptoTransaction.to_address]", primaryjoin="CryptoWallet.address==CryptoTransaction.to_address")


class CryptoTransaction(Base):
    __tablename__ = "crypto_transactions"

    id = Column(Integer, primary_key=True, index=True)
    tx_hash = Column(String, unique=True, nullable=False, index=True)
    from_address = Column(String, nullable=False, index=True)
    to_address = Column(String, nullable=False, index=True)
    amount = Column(String, nullable=True, default="UNSPECIFIED")
    currency = Column(String, nullable=False, default="BTC", index=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)


class DarknetListing(Base):
    __tablename__ = "darknet_listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    vendor_alias = Column(String, nullable=False, index=True)
    platform = Column(String, nullable=False, default="Agora", index=True)
    drug_category = Column(String, nullable=False, index=True)
    price = Column(String, nullable=True)
    currency = Column(String, nullable=True, default="BTC")
    location = Column(String, nullable=True, index=True)
    url = Column(String, nullable=True)
    scraped_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    associated_suspect_id = Column(Integer, ForeignKey("suspects.id"), nullable=True, index=True)

    suspect = relationship("Suspect", back_populates="listings")


class TelegramChannel(Base):
    __tablename__ = "telegram_channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(String, unique=True, nullable=False, index=True)
    channel_name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    member_count = Column(Integer, default=0)

    messages = relationship("TelegramMessage", back_populates="channel", cascade="all, delete-orphan")


class TelegramMessage(Base):
    __tablename__ = "telegram_messages"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("telegram_channels.id"), nullable=False, index=True)
    sender_handle = Column(String, nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    detected_wallets_json = Column(Text, nullable=True)
    detected_keywords_json = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    channel = relationship("TelegramChannel", back_populates="messages")


class NetworkTrafficFlow(Base):
    """
    Stores ingested flow analytics from Daksh's dataset collection (Darknet.CSV, Binary, MultiTotal).
    """
    __tablename__ = "network_traffic_flows"

    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(String, nullable=False, index=True)
    src_ip = Column(String, nullable=False, index=True)
    src_port = Column(Integer, nullable=True)
    dst_ip = Column(String, nullable=False, index=True)
    dst_port = Column(Integer, nullable=True)
    protocol = Column(String, nullable=True)
    timestamp_str = Column(String, nullable=True)
    encapsulation_label = Column(String, nullable=True, index=True)
    application_label = Column(String, nullable=True, index=True)
    is_encrypted = Column(Boolean, default=False, index=True)
    source_dataset = Column(String, nullable=False)


# Import and expose crawler models for metadata creation
from crawler.models import (
    Source,
    Keyword,
    CaseKeyword,
    CrawlerRun,
    RawRecord,
    RobotsCache,
)

__all__ = [
    "User",
    "RefreshSession",
    "InvestigationAccessGrant",
    "AuditLog",
    "DataProvenance",
    "Suspect",
    "CryptoWallet",
    "CryptoTransaction",
    "DarknetListing",
    "TelegramChannel",
    "TelegramMessage",
    "NetworkTrafficFlow",
    "Source",
    "Keyword",
    "CaseKeyword",
    "CrawlerRun",
    "RawRecord",
    "RobotsCache",
]

