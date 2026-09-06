"""
DB-backed alerts and suspicious activity API endpoints.

Replaces the previous mock_db.json-backed /api/alerts and /api/alerts/suspicious
endpoints with real database queries against the SuspiciousActivity and Alert models.

Uses the existing authentication (get_current_user) and RBAC (require_permission)
conventions — does not invent a new permission or auth mechanism.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User, Alert, SuspiciousActivity
from rbac import require_permission, Permission

router = APIRouter(tags=["Alerts & Suspicious Activity"])


@router.get("/api/alerts")
def get_alerts(
    severity: Optional[str] = Query(default=None, description="Filter by severity: red, yellow, green"),
    status: Optional[str] = Query(default=None, description="Filter by status: active, acknowledged, resolved"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.READ)),
):
    """
    List alerts from the database.

    Returns a list matching the frontend AlertsFeed.jsx contract:
    Each alert has: id, severity, message, timestamp, status,
    suspicious_activity_id, raw_record_id, case_id.

    Empty database returns an empty JSON array [].
    """
    query = db.query(Alert)

    if severity:
        query = query.filter(Alert.severity == severity)
    if status:
        query = query.filter(Alert.status == status)

    alerts = query.order_by(Alert.created_at.desc()).offset(offset).limit(limit).all()

    return [
        {
            "id": str(a.id),
            "severity": a.severity,
            "message": a.message,
            "timestamp": a.created_at.isoformat() if a.created_at else None,
            # Additional useful fields (frontend can ignore if not needed)
            "status": a.status,
            "suspicious_activity_id": str(a.suspicious_activity_id) if a.suspicious_activity_id else None,
            "raw_record_id": str(a.raw_record_id) if a.raw_record_id else None,
            "case_id": a.case_id,
        }
        for a in alerts
    ]


@router.get("/api/alerts/suspicious")
def get_suspicious_activity(
    status: Optional[str] = Query(default=None, description="Filter by status: open, acknowledged, resolved, dismissed"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.READ)),
):
    """
    List suspicious activities from the database.

    Returns a list matching the frontend contract:
    Each suspicious activity has: id, type, description, confidence, date,
    status, raw_record_id, case_id, evidence_summary.

    Empty database returns an empty JSON array [].
    """
    query = db.query(SuspiciousActivity)

    if status:
        query = query.filter(SuspiciousActivity.status == status)

    activities = query.order_by(SuspiciousActivity.detected_at.desc()).offset(offset).limit(limit).all()

    return [
        {
            "id": str(sa.id),
            "type": sa.activity_type,
            "description": sa.description,
            "confidence": float(sa.confidence) if sa.confidence is not None else None,
            "date": sa.detected_at.strftime("%Y-%m-%d") if sa.detected_at else None,
            # Additional useful fields
            "status": sa.status,
            "raw_record_id": str(sa.raw_record_id) if sa.raw_record_id else None,
            "case_id": sa.case_id,
            "evidence_summary": sa.evidence_summary,
        }
        for sa in activities
    ]
