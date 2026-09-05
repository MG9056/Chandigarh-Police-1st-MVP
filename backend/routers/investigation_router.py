from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from database import get_db
from models import User, Investigation, InvestigationAssignment, RoleEnum
from routers.auth_router import get_current_user
from routers.reauth_router import require_recent_reauth
from rbac import require_permission, Permission, check_investigation_modification_access_v2, check_investigation_assignment_authority
from audit_service import create_audit_log
from security import get_client_ip

router = APIRouter(prefix="/api/investigations", tags=["Investigation Management"])

# ============================================================================
# Pydantic Models for Request/Response Serialization
# ============================================================================

class InvestigationCreate(BaseModel):
    investigation_id: str
    title: str
    description: Optional[str] = None
    case_type: Optional[str] = None
    status: str = "OPEN"
    priority: int = 2
    lead_investigator_id: Optional[int] = None
    unit: Optional[str] = None

class InvestigationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    case_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    lead_investigator_id: Optional[int] = None
    unit: Optional[str] = None

class InvestigationClose(BaseModel):
    closure_reason: str
    closure_notes: Optional[str] = None

class InvestigationAssignRequest(BaseModel):
    assigned_to_id: int


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
def create_investigation(
    req: InvestigationCreate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.CREATE)),
    db: Session = Depends(get_db)
):
    """
    Create a new investigation.

    Requires CREATE permission. Investigation ID must be unique.
    """

    # Check if investigation_id already exists
    existing = db.query(Investigation).filter(Investigation.investigation_id == req.investigation_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Investigation with ID '{req.investigation_id}' already exists."
        )

    # Create investigation
    investigation = Investigation(
        investigation_id=req.investigation_id,
        title=req.title,
        description=req.description,
        case_type=req.case_type,
        status=req.status,
        priority=req.priority,
        created_by_id=current_user.id,
        lead_investigator_id=req.lead_investigator_id,
        unit=req.unit or current_user.unit
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    # Audit log (committed separately by audit_service)
    create_audit_log(
        db=db,
        action="INVESTIGATION_CREATED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "investigation_id": investigation.investigation_id,
            "title": investigation.title,
            "lead_investigator_id": investigation.lead_investigator_id
        }
    )

    return {
        "message": f"Investigation {investigation.investigation_id} created successfully",
        "investigation_id": investigation.investigation_id,
        "id": investigation.id
    }


@router.get("")
def list_investigations(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[int] = Query(None, alias="priority"),
    unit_filter: Optional[str] = Query(None, alias="unit"),
    skip: int = Query(0),
    limit: int = Query(50),
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    List investigations (filtered by status, priority, unit).

    All authenticated users can view all investigations.
    """

    query = db.query(Investigation)

    if status_filter:
        query = query.filter(Investigation.status == status_filter)
    if priority_filter is not None:
        query = query.filter(Investigation.priority == priority_filter)
    if unit_filter:
        query = query.filter(Investigation.unit == unit_filter)

    total = query.count()
    investigations = query.order_by(Investigation.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "investigations": [
            {
                "id": inv.id,
                "investigation_id": inv.investigation_id,
                "title": inv.title,
                "status": inv.status,
                "priority": inv.priority,
                "created_by": inv.created_by.email if inv.created_by else None,
                "lead_investigator": inv.lead_investigator.email if inv.lead_investigator else None,
                "unit": inv.unit,
                "created_at": inv.created_at.isoformat(),
                "updated_at": inv.updated_at.isoformat()
            }
            for inv in investigations
        ]
    }


@router.get("/{investigation_id}")
def get_investigation(
    investigation_id: str,
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    Get investigation details by investigation_id (string case number).
    """

    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    # Check permissions
    can_edit = check_investigation_modification_access_v2(current_user, investigation, db)
    can_assign = check_investigation_assignment_authority(current_user, investigation, db)

    # Serialize assignments (active only)
    assignments = [
        {
            "id": a.id,
            "assigned_to_id": a.assigned_to_id,
            "assigned_to_email": a.assigned_to.email,
            "assigned_by_id": a.assigned_by_id,
            "assigned_by_email": a.assigned_by.email,
            "assigned_at": a.assigned_at.isoformat(),
            "removed_at": a.removed_at.isoformat() if a.removed_at else None
        }
        for a in investigation.assignments if a.removed_at is None
    ]

    return {
        "id": investigation.id,
        "investigation_id": investigation.investigation_id,
        "title": investigation.title,
        "description": investigation.description,
        "case_type": investigation.case_type,
        "status": investigation.status,
        "priority": investigation.priority,
        "created_by_id": investigation.created_by_id,
        "created_by_email": investigation.created_by.email if investigation.created_by else None,
        "lead_investigator_id": investigation.lead_investigator_id,
        "lead_investigator_email": investigation.lead_investigator.email if investigation.lead_investigator else None,
        "unit": investigation.unit,
        "created_at": investigation.created_at.isoformat(),
        "updated_at": investigation.updated_at.isoformat(),
        "closed_at": investigation.closed_at.isoformat() if investigation.closed_at else None,
        "closed_by_id": investigation.closed_by_id,
        "closure_reason": investigation.closure_reason,
        "closure_notes": investigation.closure_notes,
        "assignments": assignments,
        "can_edit": can_edit,
        "can_assign": can_assign
    }


@router.patch("/{investigation_id}")
def update_investigation(
    investigation_id: str,
    req: InvestigationUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an investigation.

    Requires modification access (role-based, lead investigator, assigned, or delegation grant).
    """

    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    # Check modification access
    if not check_investigation_modification_access_v2(current_user, investigation, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this investigation."
        )

    # Update only provided fields
    if req.title is not None:
        investigation.title = req.title
    if req.description is not None:
        investigation.description = req.description
    if req.case_type is not None:
        investigation.case_type = req.case_type
    if req.status is not None:
        investigation.status = req.status
    if req.priority is not None:
        investigation.priority = req.priority
    if req.lead_investigator_id is not None:
        investigation.lead_investigator_id = req.lead_investigator_id
    if req.unit is not None:
        investigation.unit = req.unit

    investigation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(investigation)

    # Audit log
    create_audit_log(
        db=db,
        action="INVESTIGATION_UPDATED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={"updated_fields": req.model_dump(exclude_none=True)}
    )

    return {
        "message": f"Investigation {investigation.investigation_id} updated successfully",
        "investigation_id": investigation.investigation_id
    }


@router.post("/{investigation_id}/close")
def close_investigation(
    investigation_id: str,
    req: InvestigationClose,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Close an investigation.

    Requires modification access.
    """

    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    if not check_investigation_modification_access_v2(current_user, investigation, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this investigation."
        )

    if investigation.status == "CLOSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Investigation is already closed."
        )

    investigation.status = "CLOSED"
    investigation.closed_at = datetime.now(timezone.utc)
    investigation.closed_by_id = current_user.id
    investigation.closure_reason = req.closure_reason
    investigation.closure_notes = req.closure_notes
    investigation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(investigation)

    # Audit log
    create_audit_log(
        db=db,
        action="INVESTIGATION_CLOSED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "closure_reason": req.closure_reason,
            "closure_notes": req.closure_notes
        }
    )

    return {
        "message": f"Investigation {investigation.investigation_id} closed successfully",
        "investigation_id": investigation.investigation_id,
        "status": investigation.status
    }


# ============================================================================
# Assignment Management Endpoints
# ============================================================================

@router.post("/{investigation_id}/assign")
def assign_investigator(
    investigation_id: str,
    req: InvestigationAssignRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    """
    Assign an investigator to an investigation.

    Requires assignment authority (senior officer or lead investigator) + re-authentication.
    """

    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    # Check assignment authority
    if not check_investigation_assignment_authority(current_user, investigation, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to assign investigators to this investigation."
        )

    # Get target investigator
    target_user = db.query(User).filter(User.id == req.assigned_to_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {req.assigned_to_id} not found."
        )

    # Check if already actively assigned
    existing = db.query(InvestigationAssignment).filter(
        InvestigationAssignment.investigation_id == investigation.id,
        InvestigationAssignment.assigned_to_id == req.assigned_to_id,
        InvestigationAssignment.removed_at == None
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User {target_user.email} is already assigned to this investigation."
        )

    # Create assignment
    assignment = InvestigationAssignment(
        investigation_id=investigation.id,
        assigned_to_id=req.assigned_to_id,
        assigned_by_id=current_user.id
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    # Audit log
    create_audit_log(
        db=db,
        action="INVESTIGATOR_ASSIGNED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "assigned_to_user_id": req.assigned_to_id,
            "assigned_to_email": target_user.email,
            "assignment_id": assignment.id
        }
    )

    return {
        "message": f"Investigator {target_user.email} assigned to investigation {investigation.investigation_id}",
        "assignment_id": assignment.id,
        "assigned_to_id": req.assigned_to_id,
        "assigned_at": assignment.assigned_at.isoformat()
    }


@router.delete("/{investigation_id}/assign/{assignment_id}")
def remove_assignment(
    investigation_id: str,
    assignment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    """
    Remove an investigator from an investigation (soft-delete).

    Requires assignment authority + re-authentication.
    """

    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    assignment = db.query(InvestigationAssignment).filter(
        InvestigationAssignment.id == assignment_id,
        InvestigationAssignment.investigation_id == investigation.id
    ).first()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found."
        )

    if assignment.removed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This assignment has already been removed."
        )

    # Check authority
    if not check_investigation_assignment_authority(current_user, investigation, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to remove assignments from this investigation."
        )

    removed_email = assignment.assigned_to.email
    assignment.removed_at = datetime.now(timezone.utc)
    db.commit()

    # Audit log
    create_audit_log(
        db=db,
        action="INVESTIGATOR_REMOVED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "removed_user_id": assignment.assigned_to_id,
            "removed_user_email": removed_email,
            "assignment_id": assignment.id
        }
    )

    return {
        "message": f"Investigator removed from investigation {investigation.investigation_id}",
        "assignment_id": assignment.id,
        "removed_at": assignment.removed_at.isoformat()
    }


@router.get("/{investigation_id}/assignments")
def list_assignments(
    investigation_id: str,
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    List active assignments for an investigation.
    """

    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found."
        )

    assignments = db.query(InvestigationAssignment).filter(
        InvestigationAssignment.investigation_id == investigation.id,
        InvestigationAssignment.removed_at == None
    ).all()

    return {
        "investigation_id": investigation.investigation_id,
        "assignments": [
            {
                "id": a.id,
                "assigned_to_id": a.assigned_to_id,
                "assigned_to_email": a.assigned_to.email,
                "assigned_by_id": a.assigned_by_id,
                "assigned_by_email": a.assigned_by.email,
                "assigned_at": a.assigned_at.isoformat()
            }
            for a in assignments
        ]
    }

