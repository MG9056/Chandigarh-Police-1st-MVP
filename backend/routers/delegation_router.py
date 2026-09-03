from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional, List
import json

from database import get_db
from models import User, InvestigationAccessGrant, AuditLog, RoleEnum
from security import get_client_ip
from routers.auth_router import get_current_user
from routers.reauth_router import require_recent_reauth
from rbac import require_permission, Permission

router = APIRouter(prefix="/api/investigations", tags=["Investigation Access Delegation"])

class GrantAccessRequest(BaseModel):
    target_user_id: int
    permission: str = "MODIFY"
    expires_in_hours: Optional[int] = 72

class RevokeAccessRequest(BaseModel):
    grant_id: int

@router.post("/{investigation_id}/grant-access")
def grant_investigation_access(
    investigation_id: str,
    req_data: GrantAccessRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.MANAGE_ACCESS)),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    # Rule 1: A user cannot grant access to themselves
    if req_data.target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot grant access to yourself."
        )

    target_user = db.query(User).filter(User.id == req_data.target_user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )

    # Calculate expiration if specified
    expires_at = None
    if req_data.expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=req_data.expires_in_hours)

    grant = InvestigationAccessGrant(
        investigation_id=investigation_id,
        user_id=target_user.id,
        granted_by=current_user.id,
        permission=req_data.permission,
        expires_at=expires_at
    )
    db.add(grant)

    audit = AuditLog(
        user_id=current_user.id,
        role=current_user.role,
        action="ACCESS_GRANTED",
        resource_type="INVESTIGATION",
        resource_id=investigation_id,
        result="SUCCESS",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        metadata_json=json.dumps({
            "granted_to_user_id": target_user.id,
            "granted_to_email": target_user.email,
            "permission": req_data.permission
        })
    )
    db.add(audit)
    db.commit()
    db.refresh(grant)

    return {
        "message": f"Modification access granted to officer {target_user.full_name} for investigation {investigation_id}",
        "grant_id": grant.id,
        "investigation_id": investigation_id,
        "user_id": target_user.id,
        "permission": grant.permission,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None
    }

@router.post("/{investigation_id}/revoke-access")
def revoke_investigation_access(
    investigation_id: str,
    req_data: RevokeAccessRequest,
    request: Request,
    current_user: User = Depends(require_permission(Permission.MANAGE_ACCESS)),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    grant = db.query(InvestigationAccessGrant).filter(
        InvestigationAccessGrant.id == req_data.grant_id,
        InvestigationAccessGrant.investigation_id == investigation_id,
        InvestigationAccessGrant.revoked == False
    ).first()

    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active access grant not found"
        )

    grant.revoked = True
    grant.revoked_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user_id=current_user.id,
        role=current_user.role,
        action="ACCESS_REVOKED",
        resource_type="INVESTIGATION",
        resource_id=investigation_id,
        result="SUCCESS",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        metadata_json=json.dumps({"revoked_grant_id": grant.id, "revoked_user_id": grant.user_id})
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Access grant {grant.id} revoked for investigation {investigation_id}",
        "grant_id": grant.id,
        "revoked": True
    }

@router.get("/{investigation_id}/grants")
def list_investigation_access_grants(
    investigation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    grants = db.query(InvestigationAccessGrant).filter(
        InvestigationAccessGrant.investigation_id == investigation_id,
        InvestigationAccessGrant.revoked == False
    ).all()

    return [
        {
            "id": g.id,
            "investigation_id": g.investigation_id,
            "user_id": g.user_id,
            "granted_by": g.granted_by,
            "permission": g.permission,
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "expires_at": g.expires_at.isoformat() if g.expires_at else None
        }
        for g in grants
    ]
