from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, List
import csv
import io

from database import get_db
from models import User, AuditLog
from routers.auth_router import get_current_user
from routers.reauth_router import require_recent_reauth
from rbac import require_permission, Permission
from audit_service import create_audit_log

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Trail"])

@router.get("")
def list_audit_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    result: Optional[str] = None,
    request: Request = None,
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action.upper())
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type.upper())
    if result:
        query = query.filter(AuditLog.result == result.upper())
    
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            query = query.filter(AuditLog.timestamp >= dt)
        except ValueError:
            pass
    if end_date:
        try:
            dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
            query = query.filter(AuditLog.timestamp <= dt)
        except ValueError:
            pass

    logs = query.order_by(AuditLog.timestamp.desc()).limit(500).all()

    # Record viewing event
    create_audit_log(
        db=db,
        user=current_user,
        action="AUDIT_LOG_VIEWED",
        result="SUCCESS",
        request=request,
        metadata={"logs_returned_count": len(logs)}
    )

    return [
        {
            "id": l.id,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "user_id": l.user_id,
            "role": l.role,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "result": l.result,
            "ip_address": l.ip_address,
            "user_agent": l.user_agent,
            "metadata": l.metadata_json
        }
        for l in logs
    ]

@router.get("/export")
def export_audit_logs(
    request: Request,
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "User ID", "Role", "Action", "Resource Type", "Resource ID", "Result", "IP Address", "User Agent"])

    for l in logs:
        writer.writerow([
            l.id,
            l.timestamp.isoformat() if l.timestamp else "",
            l.user_id or "",
            l.role or "",
            l.action,
            l.resource_type or "",
            l.resource_id or "",
            l.result,
            l.ip_address or "",
            l.user_agent or ""
        ])

    output.seek(0)

    create_audit_log(
        db=db,
        user=current_user,
        action="AUDIT_LOG_EXPORTED",
        result="SUCCESS",
        request=request,
        metadata={"total_records_exported": len(logs)}
    )

    filename = f"darknight_audit_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
