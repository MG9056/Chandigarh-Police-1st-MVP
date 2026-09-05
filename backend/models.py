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
        return f"Assignment({self.assigned_to_id} → Investigation {self.investigation_id})"
