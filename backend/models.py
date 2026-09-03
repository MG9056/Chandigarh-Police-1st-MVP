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
