from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import json

from database import get_db
from models import User, RefreshSession, AuditLog, RoleEnum, AccountStatusEnum
from security import get_client_ip
from routers.auth_router import get_current_user

router = APIRouter(prefix="/api/admin", tags=["User Governance"])

class ApproveUserRequest(BaseModel):
    target_user_id: int
    action: str  # APPROVE or REJECT
    assigned_role: Optional[str] = RoleEnum.CONSTABLE

class SuspendUserRequest(BaseModel):
    target_user_id: int

@router.get("/users")
def list_users(status: Optional[str] = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Only INSPECTOR, SP, IGP, DGP can manage/view user governance lists
    if RoleEnum.get_rank(current_user.role) > RoleEnum.get_rank(RoleEnum.INSPECTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access user governance"
        )

    query = db.query(User)
    if status:
        query = query.filter(User.account_status == status.upper())
    
    users = query.all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "badge_number": u.badge_number,
            "unit": u.unit,
            "role": u.role,
            "account_status": u.account_status,
            "mfa_enabled": u.mfa_enabled,
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        for u in users
    ]

@router.post("/approve-user")
def approve_user(req_data: ApproveUserRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Senior role authorization check
    if RoleEnum.get_rank(current_user.role) > RoleEnum.get_rank(RoleEnum.INSPECTOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Inspectors and Senior Officers can review account approvals"
        )

    target_user = db.query(User).filter(User.id == req_data.target_user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )

    action_upper = req_data.action.upper()
    if action_upper not in ["APPROVE", "REJECT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be APPROVE or REJECT"
        )

    # CRITICAL SECURITY CONSTRAINT 4: Users cannot assign equal or higher roles than themselves!
    if action_upper == "APPROVE":
        if not req_data.assigned_role or req_data.assigned_role not in RoleEnum.hierarchy():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role specified"
            )

        approver_rank = RoleEnum.get_rank(current_user.role)
        assigned_rank = RoleEnum.get_rank(req_data.assigned_role)

        # Numerical rank: 0 (DGP) < 1 (IGP) < 2 (SP) < 3 (INSPECTOR) < 4 (INVESTIGATOR) < 5 (CONSTABLE)
        # So assigned_rank MUST BE STRICTLY GREATER THAN approver_rank!
        if assigned_rank <= approver_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Security Rule Violation: You cannot assign an equal or higher role ({req_data.assigned_role}) than your own role ({current_user.role})."
            )

        old_role = target_user.role
        target_user.account_status = AccountStatusEnum.ACTIVE
        target_user.role = req_data.assigned_role

        audit_approve = AuditLog(
            user_id=current_user.id,
            role=current_user.role,
            action="ACCOUNT_APPROVED",
            resource_type="USER",
            resource_id=str(target_user.id),
            result="SUCCESS",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            metadata_json=json.dumps({"approved_user_email": target_user.email, "role": req_data.assigned_role})
        )
        db.add(audit_approve)

        if old_role != req_data.assigned_role:
            audit_role = AuditLog(
                user_id=current_user.id,
                role=current_user.role,
                action="ROLE_CHANGED",
                resource_type="USER",
                resource_id=str(target_user.id),
                result="SUCCESS",
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent"),
                metadata_json=json.dumps({"old_role": old_role, "new_role": req_data.assigned_role})
            )
            db.add(audit_role)

    else:
        target_user.account_status = AccountStatusEnum.REJECTED
        audit_reject = AuditLog(
            user_id=current_user.id,
            role=current_user.role,
            action="ACCOUNT_REJECTED",
            resource_type="USER",
            resource_id=str(target_user.id),
            result="SUCCESS",
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            metadata_json=json.dumps({"rejected_user_email": target_user.email})
        )
        db.add(audit_reject)

    db.commit()
    return {
        "message": f"User account successfully {action_upper.lower()}d",
        "target_user_id": target_user.id,
        "account_status": target_user.account_status,
        "assigned_role": target_user.role
    }

@router.post("/suspend-user")
def suspend_user(req_data: SuspendUserRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if RoleEnum.get_rank(current_user.role) > RoleEnum.get_rank(RoleEnum.SP):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only SPs and Senior Officers can suspend accounts"
        )

    target_user = db.query(User).filter(User.id == req_data.target_user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found"
        )

    # Cannot suspend equal or higher role
    if RoleEnum.get_rank(target_user.role) <= RoleEnum.get_rank(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot suspend an officer of equal or higher rank"
        )

    target_user.account_status = AccountStatusEnum.SUSPENDED

    # Instantly revoke all active refresh sessions for suspended user (PRD S-04)
    sessions = db.query(RefreshSession).filter(
        RefreshSession.user_id == target_user.id,
        RefreshSession.revoked == False
    ).all()
    for s in sessions:
        s.revoked = True

    audit = AuditLog(
        user_id=current_user.id,
        role=current_user.role,
        action="ACCOUNT_SUSPENDED",
        resource_type="USER",
        resource_id=str(target_user.id),
        result="SUCCESS",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        metadata_json=json.dumps({"suspended_user_email": target_user.email})
    )
    db.add(audit)
    db.commit()

    return {
        "message": "User account suspended and active sessions revoked",
        "target_user_id": target_user.id,
        "account_status": target_user.account_status
    }
