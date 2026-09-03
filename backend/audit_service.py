from sqlalchemy.orm import Session
from datetime import datetime, timezone
from fastapi import Request
import json

from models import AuditLog, User
from security import get_client_ip

# Sensitive field keys to strictly sanitize and strip out of metadata
SENSITIVE_KEYS = {"password", "password_hash", "jwt", "access_token", "refresh_token", "api_key", "secret", "totp_secret"}

def sanitize_metadata(metadata: dict) -> str:
    """Sanitizes metadata dictionary removing passwords, tokens, and secrets before persisting."""
    if not metadata:
        return None
    clean = {}
    for k, v in metadata.items():
        if k.lower() in SENSITIVE_KEYS:
            clean[k] = "[REDACTED]"
        else:
            clean[k] = v
    return json.dumps(clean)

def create_audit_log(
    db: Session,
    action: str,
    result: str,
    user: User = None,
    resource_type: str = None,
    resource_id: str = None,
    request: Request = None,
    metadata: dict = None
) -> AuditLog:
    """
    Appends a new security/investigation audit record to the database.
    No UPDATE or DELETE endpoints exist for audit records.
    """
    user_id = user.id if user else None
    role = user.role if user else None
    ip_address = get_client_ip(request) if request else None
    user_agent = request.headers.get("User-Agent") if request else None

    audit_entry = AuditLog(
        user_id=user_id,
        role=role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=sanitize_metadata(metadata)
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry
