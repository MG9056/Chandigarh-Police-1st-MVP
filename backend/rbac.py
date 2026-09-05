from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Callable, Optional
from datetime import datetime, timezone

from database import get_db
from models import User, InvestigationAccessGrant, RoleEnum, AccountStatusEnum
from models import User, InvestigationAccessGrant, RoleEnum, AccountStatusEnum, Investigation, InvestigationAssignment
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


def check_investigation_view_access(user: User, investigation: Investigation, db: Session) -> bool:
    """
    Validates whether a user can view an investigation.

    Current policy (Step 1): ALL roles can view all investigations.
    This implements broad visibility across the police hierarchy.
    """
    return True  # Everyone can view


def check_investigation_modification_access_v2(user: User, investigation: Investigation, db: Session) -> bool:
    """
    Enhanced version of check_investigation_modification_access.
    Checks both new Investigation table AND existing InvestigationAccessGrant for backward compatibility.

    Authorization rules (in order of precedence):
    1. SUPER_ADMIN/DGP → can edit any investigation
    2. IGP → can edit any investigation
    3. SP → can edit investigations in own unit (User.unit == Investigation.unit)
    4. INSPECTOR → can edit investigations in own unit
    5. Investigation Lead Investigator → can edit their own case
    6. Explicitly Assigned via InvestigationAssignment table → can edit
    7. Has active InvestigationAccessGrant (legacy delegation) → can edit
    8. Everyone else → denied
    """

    # Rule 1-2: Senior officers have global scope
    if user.role in [RoleEnum.SUPER_ADMIN, RoleEnum.IGP]:
        return True

    # Rule 3-4: SP/Inspector check unit match
    if user.role in [RoleEnum.SP, RoleEnum.INSPECTOR]:
        if user.unit and investigation.unit and user.unit == investigation.unit:
            return True

    # Rule 5: User is the lead investigator
    if investigation.lead_investigator_id == user.id:
        return True

    # Rule 6: User is explicitly assigned via InvestigationAssignment table
    assignment = db.query(InvestigationAssignment).filter(
        InvestigationAssignment.investigation_id == investigation.id,
        InvestigationAssignment.assigned_to_id == user.id,
        InvestigationAssignment.removed_at == None  # Active assignment only
    ).first()
    if assignment:
        return True

    # Rule 7: Check existing delegated access grants (backward compatibility)
    # This uses the string investigation_id to look up existing grants
    grant = db.query(InvestigationAccessGrant).filter(
        InvestigationAccessGrant.user_id == user.id,
        InvestigationAccessGrant.investigation_id == investigation.investigation_id,
        InvestigationAccessGrant.revoked == False,
        InvestigationAccessGrant.permission == "MODIFY"
    ).first()

    if grant:
        # Check if grant has expired
        expires_at = grant.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at is None or expires_at > datetime.now(timezone.utc):
            return True

    # Rule 8: Denied
    return False


def check_investigation_assignment_authority(user: User, investigation: Investigation, db: Session) -> bool:
    """
    Who can assign investigators to an investigation?

    Rules:
    - SUPER_ADMIN/IGP → can assign to any investigation
    - SP/INSPECTOR → can assign to investigations in own unit, AND must be the lead investigator
    - Others → denied
    """

    if user.role in [RoleEnum.SUPER_ADMIN, RoleEnum.IGP]:
        return True

    if user.role in [RoleEnum.SP, RoleEnum.INSPECTOR]:
        # Must be in same unit AND be the lead investigator
        if user.unit == investigation.unit and investigation.lead_investigator_id == user.id:
            return True

    return False
