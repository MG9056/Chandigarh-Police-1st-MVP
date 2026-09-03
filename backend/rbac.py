from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Callable, Optional
from datetime import datetime, timezone

from database import get_db
from models import User, InvestigationAccessGrant, RoleEnum, AccountStatusEnum
from routers.auth_router import get_current_user

class Permission:
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EXPORT = "EXPORT"
    MANAGE_ACCESS = "MANAGE_ACCESS"
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_DATA_SOURCES = "MANAGE_DATA_SOURCES"
    MANAGE_PIPELINES = "MANAGE_PIPELINES"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"

# Role -> Default Permissions Matrix
ROLE_PERMISSIONS = {
    RoleEnum.SUPER_ADMIN: {
        Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE,
        Permission.EXPORT, Permission.MANAGE_ACCESS, Permission.MANAGE_USERS,
        Permission.MANAGE_DATA_SOURCES, Permission.MANAGE_PIPELINES, Permission.VIEW_AUDIT_LOGS
    },
    RoleEnum.IGP: {
        Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE,
        Permission.EXPORT, Permission.MANAGE_ACCESS, Permission.MANAGE_USERS,
        Permission.MANAGE_DATA_SOURCES, Permission.MANAGE_PIPELINES, Permission.VIEW_AUDIT_LOGS
    },
    RoleEnum.SP: {
        Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.EXPORT,
        Permission.MANAGE_ACCESS, Permission.MANAGE_USERS, Permission.VIEW_AUDIT_LOGS
    },
    RoleEnum.INSPECTOR: {
        Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.MANAGE_ACCESS,
        Permission.EXPORT
    },
    RoleEnum.INVESTIGATOR: {
        Permission.READ, Permission.CREATE, Permission.UPDATE
    },
    RoleEnum.CONSTABLE: {
        Permission.READ
    }
}

def has_permission(user_role: str, permission: str) -> bool:
    """Checks if a user role possesses a specific default permission."""
    allowed_perms = ROLE_PERMISSIONS.get(user_role, set())
    return permission in allowed_perms

def require_permission(required_permission: str):
    """
    FastAPI dependency factory enforcing that the authenticated user possesses the required permission.
    Returns HTTP 403 Forbidden if unauthorized.
    """
    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user.role, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Authorization Failure: Permission '{required_permission}' is required for this operation."
            )
        return current_user
    return permission_checker

def check_investigation_modification_access(user: User, investigation_id: str, db: Session) -> bool:
    """
    Validates whether a user is authorized to modify a specific investigation.
    Senior roles (DGP, IGP, SP) have general modification authority.
    Lower roles (Investigator, Constable) require assigned scope or explicit delegated grant.
    """
    # 1. Senior Officers have global/district modification scope
    if user.role in [RoleEnum.SUPER_ADMIN, RoleEnum.IGP, RoleEnum.SP]:
        return True

    # 2. Inspectors have unit modification scope
    if user.role == RoleEnum.INSPECTOR:
        return True

    # 3. Check explicit delegated access grant using composite index (user_id, investigation_id)
    grant = db.query(InvestigationAccessGrant).filter(
        InvestigationAccessGrant.user_id == user.id,
        InvestigationAccessGrant.investigation_id == investigation_id,
        InvestigationAccessGrant.revoked == False,
        InvestigationAccessGrant.permission == "MODIFY"
    ).first()

    if grant:
        # Handle timezone awareness for naive SQLite datetimes
        expires_at = grant.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at is None or expires_at > datetime.now(timezone.utc):
            return True

    return False
