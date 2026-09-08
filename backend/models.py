from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index, JSON, Numeric

from sqlalchemy.orm import relationship, synonym
from sqlalchemy import Uuid
from uuid import uuid4
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

class InvestigationFindingStatus:
    """Valid review statuses for InvestigationFinding."""
    PENDING_REVIEW = "PENDING_REVIEW"
    RELEVANT = "RELEVANT"
    DISMISSED = "DISMISSED"

    @classmethod
    def all_values(cls):
        return [cls.PENDING_REVIEW, cls.RELEVANT, cls.DISMISSED]


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

    Extended for evidence promotion (Step 3):
    - finding_id: FK to InvestigationFinding when promoted from a human review decision
    - raw_record_id: UUID string of the source RawRecord (denormalised for fast lookup)
    - promoted_by_id: FK to User who performed the promotion
    - promoted_at: timestamp of promotion action
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

    # Evidence promotion fields (Step 3)
    finding_id = Column(Integer, ForeignKey("investigation_findings.id"), nullable=True, index=True)
    raw_record_id = Column(String, nullable=True, index=True)
    promoted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    promoted_at = Column(DateTime(timezone=True), nullable=True)


class SuspiciousActivityStatusEnum:
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"

class AlertStatusEnum:
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class SuspiciousActivity(Base):
    """
    Detected suspicious pattern/event derived from a RawRecord.
    Preserves the distinction between original collected data (RawRecord)
    and derived detection/AI analysis (this model).
    """
    __tablename__ = "suspicious_activities"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    raw_record_id = Column(Uuid(as_uuid=True), ForeignKey("raw_records.id"), nullable=True, index=True)
    case_id = Column(String, nullable=True, index=True)
    activity_type = Column(String, nullable=False, index=True)  # high_relevance, keyword_burst, entity_indicator, combined_signal
    description = Column(Text, nullable=False)
    confidence = Column(Numeric, nullable=False)  # Detection/risk confidence score 0.0–1.0
    evidence_summary = Column(JSON, nullable=True)  # Explainable reasons array
    status = Column(String, nullable=False, default=SuspiciousActivityStatusEnum.OPEN)
    detected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    alerts = relationship("Alert", back_populates="suspicious_activity")

    __table_args__ = (
        Index("idx_sa_raw_record_type", "raw_record_id", "activity_type"),
    )

class Alert(Base):
    """
    Actionable notification generated from a suspicious activity detection.
    Uses dedup_key to prevent duplicate alerts for the same underlying detection.
    """
    __tablename__ = "alerts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    suspicious_activity_id = Column(Uuid(as_uuid=True), ForeignKey("suspicious_activities.id"), nullable=True, index=True)
    raw_record_id = Column(Uuid(as_uuid=True), ForeignKey("raw_records.id"), nullable=True, index=True)
    case_id = Column(String, nullable=True, index=True)
    severity = Column(String, nullable=False)  # "red", "yellow", "green"
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default=AlertStatusEnum.ACTIVE)
    dedup_key = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    suspicious_activity = relationship("SuspiciousActivity", back_populates="alerts")

    # Evidence promotion fields (Step 3) — all nullable for backward compatibility
    finding_id = Column(Integer, ForeignKey("investigation_findings.id"), nullable=True, index=True)
      # RawRecord.id as string (UUID)
    promoted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    promoted_at = Column(DateTime(timezone=True), nullable=True)


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

class CrawlerCandidate(Base):
    __tablename__ = "crawler_candidates"

    id = Column(Integer, primary_key=True, index=True)
    source_record_id = Column(Uuid(as_uuid=True), ForeignKey("raw_records.id"), nullable=True, unique=True, index=True)
    case_id = Column(String, nullable=True, index=True)
    primary_alias = Column(String, nullable=True, index=True)
    aliases_json = Column(Text, nullable=True)
    telegram_handle = Column(String, nullable=True, index=True)
    phone_number = Column(String, nullable=True, index=True)
    last_known_location = Column(String, nullable=True, index=True)
    platform_mentions = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    cleaned_text = Column(Text, nullable=True)
    source_url = Column(String, nullable=True)
    confidence_score = Column(Numeric, nullable=True, default=0.0)
    risk_score = Column(Integer, default=35, index=True)
    data_origin = Column(String, nullable=False, default="crawler_candidate", index=True)
    synthetic_generated = Column(Boolean, default=True, nullable=False)
    synthetic_reason = Column(String, nullable=True)
    status = Column(String, nullable=False, default="crawler_candidate")
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class Suspect(Base):
    __tablename__ = "suspects"

    id = Column(Integer, primary_key=True, index=True)
    primary_alias = Column(String, nullable=False, index=True)
    aliases_json = Column(Text, nullable=True)          # JSON list of known handles/aliases
    pgp_fingerprint = Column(String, nullable=True, index=True)
    phone_number = Column(String, nullable=True, index=True)
    last_known_location = Column(String, nullable=True, index=True)
    platform_mentions = Column(Text, nullable=True)
    enrichment_summary = Column(Text, nullable=True)
    enrichment_source_count = Column(Integer, nullable=True, default=0)
    last_enriched_at = Column(DateTime(timezone=True), nullable=True)
    data_origin = Column(String, nullable=True, index=True)
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
    listing_id = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    vendor_name = Column(String, nullable=False, index=True)
    marketplace = Column(String, nullable=False, index=True)

    description = Column(Text, nullable=True)

    drug_category = Column(String, nullable=False, index=True)
    price = Column(String, nullable=True)
    currency = Column(String, nullable=True, default="BTC")
    location = Column(String, nullable=True, index=True)
    url = Column(String, nullable=True)
    scraped_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    associated_suspect_id = Column(Integer, ForeignKey("suspects.id"), nullable=True, index=True)

    vendor_alias = synonym("vendor_name")
    platform = synonym("marketplace")

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

    source_dataset = Column(String, nullable=False)                 # Darknet.CSV, Binary, MultiTotal


class Investigation(Base):
    """
    Core Investigation entity for Step 1.

    Design notes:
    - `investigation_id` (string) matches existing delegation system's investigation_id
    - `id` (integer) is the primary key for FK relationships
    - `unit` is a string (free-form) for now; Step 2 will add District/PoliceStation FKs
    - `status` is one of: OPEN, ACTIVE, CLOSED
    - `priority` is 1-4: Low, Medium, High, Critical

    Future Steps 2-3 will add relationships to:
    - Keywords (via investigation-specific keyword association)
    - Sources/Crawlers (via source assignment)
    - Raw Intelligence Records (via evidence/findings)
    - Audit Activity Timeline (via audit system integration)
    - Entity Graph (via entity correlation)
    - Geographic Hotspots (via geo signals)
    """
    __tablename__ = "investigations"

    # Identifier & Metadata
    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(String, unique=True, index=True, nullable=False)  # User-facing case number
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    case_type = Column(String, nullable=True)  # E.g., "Drug Trafficking", "Financial Crime"

    # Status & Priority
    status = Column(String, nullable=False, default="OPEN")  # OPEN, ACTIVE, CLOSED
    priority = Column(Integer, nullable=False, default=2)  # 1=Low, 2=Medium, 3=High, 4=Critical

    # Personnel
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    lead_investigator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    closed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Jurisdiction (Step 1: just string to match User.unit; Step 2+ will add FK to District/PoliceStation)
    unit = Column(String, nullable=True)  # Free-form unit/district string, matches User.unit

    # Lifecycle
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closure_reason = Column(String, nullable=True)
    closure_notes = Column(Text, nullable=True)

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id], lazy="joined")
    lead_investigator = relationship("User", foreign_keys=[lead_investigator_id], lazy="joined")
    closed_by = relationship("User", foreign_keys=[closed_by_id], lazy="joined")
    assignments = relationship("InvestigationAssignment", back_populates="investigation", cascade="all, delete-orphan", lazy="joined")

    __table_args__ = (
        Index("idx_investigation_status_priority", "status", "priority"),
        Index("idx_investigation_lead", "lead_investigator_id"),
        Index("idx_investigation_unit", "unit"),
    )

    def __str__(self):
        return f"Investigation({self.investigation_id}: {self.title})"


class InvestigationAssignment(Base):
    """
    Tracks investigator assignments to investigations.

    Supports:
    - Multiple investigators assigned to one investigation
    - Audit trail of who assigned whom and when
    - Removal of investigators (soft-delete via removed_at)

    Step 1 only tracks assignments. Step 3 will integrate with activity timeline.
    """
    __tablename__ = "investigation_assignments"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=False, index=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    removed_at = Column(DateTime(timezone=True), nullable=True)  # Soft-delete

    # Relationships
    investigation = relationship("Investigation", back_populates="assignments")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], lazy="joined")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id], lazy="joined")

    __table_args__ = (
        Index("idx_assignment_investigation_user", "investigation_id", "assigned_to_id"),
        Index("idx_assignment_active", "investigation_id", "removed_at"),
    )

    def __str__(self):
        return f"Assignment({self.assigned_to_id} -> Investigation {self.investigation_id})"


class InvestigationSource(Base):
    """
    Association table: which global Source objects are attached to which Investigation.

    Allows investigations to reuse sources without making sources investigation-specific.
    Soft-deleted via removed_at to preserve audit trail.
    """
    __tablename__ = "investigation_sources"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=False, index=True)
    source_id = Column(String, nullable=False, index=True)  # UUID string matching Source.id
    added_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    added_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    removed_at = Column(DateTime(timezone=True), nullable=True)  # Soft-delete: when detached

    # Relationships
    investigation = relationship("Investigation", lazy="joined")
    added_by = relationship("User", foreign_keys=[added_by_id], lazy="joined")

    __table_args__ = (
        Index("idx_investigation_source", "investigation_id", "source_id"),
        Index("idx_investigation_sources_active", "investigation_id", "removed_at"),
    )

    def __str__(self):
        return f"InvestigationSource({self.investigation_id} -> {self.source_id})"


class InvestigationFinding(Base):
    """
    Investigator review decision on a RawRecord within an investigation.

    One row per (investigation, raw_record) pair.
    Upsert on review: if finding already exists, update status+notes.

    Important: RawRecord is immutable crawler output.
    Finding is investigator's decision (can be changed).
    """
    __tablename__ = "investigation_findings"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=False, index=True)
    raw_record_id = Column(String, nullable=False, index=True)  # RawRecord.id (UUID string)
    review_status = Column(String, nullable=False, default="PENDING_REVIEW")
    # VALID VALUES: "PENDING_REVIEW", "RELEVANT", "DISMISSED"
    review_notes = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    investigation = relationship("Investigation", lazy="joined")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id], lazy="joined")

    __table_args__ = (
        Index("idx_investigation_finding", "investigation_id", "raw_record_id"),
        Index("idx_investigation_findings_status", "investigation_id", "review_status"),
    )

    def __str__(self):
        return f"InvestigationFinding({self.investigation_id} / {self.raw_record_id} -> {self.review_status})"


# Import and expose crawler models so Base.metadata.create_all() creates their tables
from crawler.models import (
    Source,
    Keyword,
    CaseKeyword,
    CrawlerRun,
    RawRecord,
    RobotsCache,
)


class InvestigationAlertStatus:
    """Valid status values for InvestigationAlert."""
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"

    @classmethod
    def all_values(cls):
        return [cls.OPEN, cls.ACKNOWLEDGED, cls.RESOLVED]


class InvestigationAlert(Base):
    """
    Alert raised against an investigation, optionally linked to a RawRecord or Finding.

    Severity levels: LOW, MEDIUM, HIGH, CRITICAL
    Status lifecycle: OPEN → ACKNOWLEDGED → RESOLVED

    Global read: anyone with READ permission can view alerts.
    Global mutation (resolve/delete): DGP/IGP only (can_manage_global_alerts).
    Investigation-scoped mutation (create/resolve own): v2 modification access + reauth.
    """
    __tablename__ = "investigation_alerts"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id"), nullable=False, index=True)
    raw_record_id = Column(String, nullable=True, index=True)  # optional link to RawRecord
    finding_id = Column(Integer, ForeignKey("investigation_findings.id"), nullable=True)
    severity = Column(String, nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default=InvestigationAlertStatus.OPEN)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_alert_investigation_status", "investigation_id", "status"),
    )


class Report(Base):
    """
    Generated Intelligence & Evidence Report for an Investigation.

    Preserves AI-generated analysis, structured sections, and grounding links
    to the source DataProvenance and RawRecords without modifying original evidence.
    """
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, unique=True, index=True, nullable=False)
    investigation_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    structured_data = Column(JSON, nullable=True)
    evidence_references = Column(JSON, nullable=True)
    model_used = Column(String, nullable=False)
    status = Column(String, nullable=False, default="GENERATED")  # DRAFT, GENERATED, FINALIZED
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id], lazy="joined")
    investigation = relationship(
        "Investigation",
        primaryjoin="Report.investigation_id == foreign(Investigation.investigation_id)",
        lazy="joined",
    )

    __table_args__ = (
        Index("idx_reports_investigation_id", "investigation_id"),
    )

    def __str__(self):
        return f"Report({self.report_id}: {self.title})"


__all__ = [
    # Core application models
    "User",
    "RefreshSession",
    "InvestigationAccessGrant",
    "AuditLog",
    "DataProvenance",
    # Alerts & Suspicious Activity
    "SuspiciousActivity",
    "SuspiciousActivityStatusEnum",
    "Alert",
    "AlertStatusEnum",
    # Domain & Intelligence Models
    "Suspect",
    "CryptoWallet",
    "CryptoTransaction",
    "DarknetListing",
    "TelegramChannel",
    "TelegramMessage",
    "NetworkTrafficFlow",
    # Investigation management models (Step 1, 2 & 3)
    "Investigation",
    "InvestigationAssignment",
    "InvestigationFindingStatus",
    "InvestigationSource",
    "InvestigationFinding",
    "InvestigationAlertStatus",
    "InvestigationAlert",
    "Report",
    # Crawler subsystem models
    "Source",
    "Keyword",
    "CaseKeyword",
    "CrawlerRun",
    "RawRecord",
    "RobotsCache",
]


