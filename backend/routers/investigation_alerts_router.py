"""
Investigation Alerts Router — Step 3

Manages alerts raised against investigations. Provides both investigation-scoped
and global endpoints.

Route summary:
  Investigation-scoped (prefix: /api/investigations/{investigation_id}/alerts):
    GET    ""                       → list alerts, optional ?status= filter (READ)
    POST   ""                       → create alert (v2 mod access + reauth)
    POST   "/{alert_id}/resolve"    → resolve alert (v2 mod access + reauth)

  Global (registered in main.py or via a top-level prefix):
    GET    /api/alerts              → global unscoped list (READ)
    DELETE /api/alerts/{alert_id}   → hard delete, DGP/IGP only + reauth

Authorization notes:
  - Global alert deletion is restricted to can_manage_global_alerts (DGP/IGP).
  - The legacy /api/alerts/suspicious mock endpoint in main.py is UNTOUCHED.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from audit_service import create_audit_log
from database import get_db
from models import (
    Investigation,
    InvestigationAlert,
    InvestigationAlertStatus,
    User,
)
from rbac import (
    can_manage_global_alerts,
    check_investigation_modification_access_v2,
    require_permission,
    Permission,
)
from routers.auth_router import get_current_user
from routers.reauth_router import require_recent_reauth

# ── Investigation-scoped router ─────────────────────────────────────────────
router = APIRouter(
    prefix="/api/investigations/{investigation_id}/alerts",
    tags=["Investigation Alerts"],
)

# ── Global alerts router (registered separately in main.py) ─────────────────
global_alerts_router = APIRouter(
    prefix="/api/alerts",
    tags=["Global Alerts"],
)


# ── Pydantic models ──────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    title: str
    severity: str = "MEDIUM"  # LOW | MEDIUM | HIGH | CRITICAL
    description: Optional[str] = None
    raw_record_id: Optional[str] = None
    finding_id: Optional[int] = None


# ── Investigation-scoped endpoints ───────────────────────────────────────────

@router.get("")
def list_investigation_alerts(
    investigation_id: str,
    alert_status: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0),
    limit: int = Query(50),
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db),
):
    """List alerts for an investigation. Optional ?status= filter (OPEN/ACKNOWLEDGED/RESOLVED)."""
    investigation = db.query(Investigation).filter(
        Investigation.investigation_id == investigation_id
    ).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    query = db.query(InvestigationAlert).filter(
        InvestigationAlert.investigation_id == investigation.id
    )
    if alert_status:
        if alert_status.upper() not in InvestigationAlertStatus.all_values():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {InvestigationAlertStatus.all_values()}",
            )
        query = query.filter(InvestigationAlert.status == alert_status.upper())

    total = query.count()
    alerts = query.order_by(InvestigationAlert.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "investigation_id": investigation_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "alerts": [_serialize_alert(a) for a in alerts],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_investigation_alert(
    investigation_id: str,
    req: AlertCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db),
):
    """Create an alert for an investigation. Requires modification access + re-auth."""
    investigation = db.query(Investigation).filter(
        Investigation.investigation_id == investigation_id
    ).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    if not check_investigation_modification_access_v2(current_user, investigation, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create alerts for this investigation.",
        )

    severity = req.severity.upper()
    if severity not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="severity must be one of: LOW, MEDIUM, HIGH, CRITICAL",
        )

    alert = InvestigationAlert(
        investigation_id=investigation.id,
        title=req.title,
        severity=severity,
        description=req.description,
        raw_record_id=req.raw_record_id,
        finding_id=req.finding_id,
        status=InvestigationAlertStatus.OPEN,
        created_by_id=current_user.id,
    )
    db.add(alert)

    create_audit_log(
        db=db,
        action="ALERT_CREATED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "alert_title": req.title,
            "severity": severity,
            "raw_record_id": req.raw_record_id,
            "finding_id": req.finding_id,
        },
    )

    db.commit()
    db.refresh(alert)

    return {
        "message": "Alert created",
        "alert_id": alert.id,
        **_serialize_alert(alert),
    }


@router.post("/{alert_id}/resolve")
def resolve_investigation_alert(
    investigation_id: str,
    alert_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db),
):
    """Resolve an alert. Requires modification access + re-auth."""
    investigation = db.query(Investigation).filter(
        Investigation.investigation_id == investigation_id
    ).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    if not check_investigation_modification_access_v2(current_user, investigation, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to resolve alerts for this investigation.",
        )

    alert = db.query(InvestigationAlert).filter(
        InvestigationAlert.id == alert_id,
        InvestigationAlert.investigation_id == investigation.id,
    ).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found for this investigation.",
        )

    if alert.status == InvestigationAlertStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is already resolved.",
        )

    alert.status = InvestigationAlertStatus.RESOLVED
    alert.resolved_by_id = current_user.id
    alert.resolved_at = datetime.now(timezone.utc)

    create_audit_log(
        db=db,
        action="ALERT_RESOLVED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={"alert_id": alert_id, "alert_title": alert.title},
    )

    db.commit()
    db.refresh(alert)

    return {"message": "Alert resolved", **_serialize_alert(alert)}


# ── Global alert endpoints ───────────────────────────────────────────────────

@global_alerts_router.get("")
def list_global_alerts(
    alert_status: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0),
    limit: int = Query(50),
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db),
):
    """
    Global unscoped alert list across all investigations.

    Read-only; broad access. For investigation-scoped alerts use
    GET /api/investigations/{id}/alerts.
    """
    query = db.query(InvestigationAlert)
    if alert_status:
        if alert_status.upper() not in InvestigationAlertStatus.all_values():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {InvestigationAlertStatus.all_values()}",
            )
        query = query.filter(InvestigationAlert.status == alert_status.upper())

    total = query.count()
    alerts = query.order_by(InvestigationAlert.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "alerts": [_serialize_alert(a) for a in alerts],
    }


@global_alerts_router.delete("/{alert_id}", status_code=status.HTTP_200_OK)
def delete_global_alert(
    alert_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db),
):
    """
    Hard-delete an alert (any investigation). DGP/IGP only + re-auth.

    This is a global administrative action; investigation leads cannot hard-delete
    each other's alerts — they can only resolve their own via the scoped endpoint.
    """
    if not can_manage_global_alerts(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only DGP/IGP officers can permanently delete alerts.",
        )

    alert = db.query(InvestigationAlert).filter(InvestigationAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found.",
        )

    create_audit_log(
        db=db,
        action="ALERT_DELETED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=str(alert.investigation_id),
        request=request,
        metadata={"alert_id": alert_id, "alert_title": alert.title},
    )

    db.delete(alert)
    db.commit()

    return {"message": f"Alert {alert_id} permanently deleted."}


# ── Serializer helper ────────────────────────────────────────────────────────

def _serialize_alert(a: InvestigationAlert) -> dict:
    return {
        "id": a.id,
        "investigation_id": a.investigation_id,
        "severity": a.severity,
        "title": a.title,
        "description": a.description,
        "status": a.status,
        "raw_record_id": a.raw_record_id,
        "finding_id": a.finding_id,
        "created_by_id": a.created_by_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "resolved_by_id": a.resolved_by_id,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }
