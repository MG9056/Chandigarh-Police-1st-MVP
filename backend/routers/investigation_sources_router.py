import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from audit_service import create_audit_log
from crawler.orchestration.flows import run_crawl
from database import get_db
from models import Investigation, InvestigationSource, Source, User
from rbac import can_manage_investigation_sources, require_permission, Permission

from routers.auth_router import get_current_user
from routers.reauth_router import require_recent_reauth
from security import get_client_ip, parse_uuid_safely

router = APIRouter(prefix="/api/investigations/{investigation_id}/sources", tags=["Investigation Sources"])

# ============================================================================
# Pydantic Models
# ============================================================================

class AttachSourceRequest(BaseModel):
    source_id: str  # String representation of Source UUID or ID


class SourceDetailResponse(BaseModel):
    id: int
    investigation_id: int
    source_id: str
    added_by_id: Optional[int]
    added_by_email: Optional[str]
    added_at: str
    removed_at: Optional[str]

    class Config:
        from_attributes = True

# ============================================================================
# Endpoints
# ============================================================================

@router.get("")
def list_investigation_sources(
    investigation_id: str,
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    List sources currently attached to an investigation (active, not detached).
    All authenticated users can view.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    # Get active source attachments
    attachments = db.query(InvestigationSource).filter(
        InvestigationSource.investigation_id == investigation.id,
        InvestigationSource.removed_at == None
    ).all()

    # Get source details for enriched response
    sources_data = []
    for a in attachments:
        source_uuid = parse_uuid_safely(a.source_id, field_name="source_id", allow_none=True) if a.source_id else None
        source = db.query(Source).filter(Source.id == source_uuid).first() if source_uuid else None
        sources_data.append({
            "id": a.id,
            "source_id": str(a.source_id),
            "source_name": source.name if source else f"Source-{a.source_id}",
            "source_type": source.source_type if source else "Unknown",
            "added_by_id": a.added_by_id,
            "added_by_email": a.added_by.email if a.added_by else None,
            "added_at": a.added_at.isoformat()
        })

    return {
        "investigation_id": investigation_id,
        "sources": sources_data
    }


@router.post("")
def attach_source_to_investigation(
    investigation_id: str,
    req: AttachSourceRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Attach an existing crawler source to an investigation.
    Requires investigation modification access.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    if not can_manage_investigation_sources(current_user, investigation, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to attach sources to this investigation.")

    # Verify source exists
    source_uuid = parse_uuid_safely(req.source_id, field_name="source_id")
    source = db.query(Source).filter(Source.id == source_uuid).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source '{req.source_id}' not found.")

    # Check if already attached (active)
    existing = db.query(InvestigationSource).filter(
        InvestigationSource.investigation_id == investigation.id,
        InvestigationSource.source_id == str(source.id),
        InvestigationSource.removed_at == None
    ).first()

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Source '{source.name}' is already attached to this investigation.")

    # Create new attachment (even if one was previously detached)
    attachment = InvestigationSource(
        investigation_id=investigation.id,
        source_id=str(source.id),
        added_by_id=current_user.id
    )
    db.add(attachment)

    create_audit_log(
        db=db,
        action="INVESTIGATION_SOURCE_ATTACHED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={"source_id": str(source.id), "source_name": source.name}
    )

    db.commit()
    db.refresh(attachment)

    return {
        "message": f"Source '{source.name}' attached to investigation {investigation_id}",
        "source_id": str(source.id),
        "attached": True
    }


@router.delete("/{source_id}")
def detach_source_from_investigation(
    investigation_id: str,
    source_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    """
    Detach a source from an investigation (soft-delete).
    The global Source is not deleted; only this association is marked removed.
    Requires investigation modification access + re-authentication.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    if not can_manage_investigation_sources(current_user, investigation, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to detach sources.")

    # Find active attachment
    attachment = db.query(InvestigationSource).filter(
        InvestigationSource.investigation_id == investigation.id,
        InvestigationSource.source_id == source_id,
        InvestigationSource.removed_at == None
    ).first()

    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source '{source_id}' is not attached to this investigation.")

    # Soft-delete
    attachment.removed_at = datetime.now(timezone.utc)

    source_uuid = parse_uuid_safely(source_id, field_name="source_id")
    source = db.query(Source).filter(Source.id == source_uuid).first()

    create_audit_log(
        db=db,
        action="INVESTIGATION_SOURCE_DETACHED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={"source_id": source_id, "source_name": source.name if source else "Unknown"}
    )

    db.commit()

    return {"message": f"Source detached successfully", "source_id": source_id, "detached": True}


@router.post("/{source_id}/trigger")
async def trigger_source_for_investigation(
    investigation_id: str,
    source_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger a crawler run for an attached source in investigation context.

    The crawl will run with case_id = investigation.investigation_id
    so that RawRecords and CrawlerRun.case_id are scoped to this investigation.

    Requires source attachment.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    if not can_manage_investigation_sources(current_user, investigation, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to trigger sources.")

    # Verify source is attached (active)
    attachment = db.query(InvestigationSource).filter(
        InvestigationSource.investigation_id == investigation.id,
        InvestigationSource.source_id == source_id,
        InvestigationSource.removed_at == None
    ).first()

    if not attachment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Source '{source_id}' is not attached to this investigation.")

    # Verify source exists
    source_uuid = parse_uuid_safely(source_id, field_name="source_id")
    source = db.query(Source).filter(Source.id == source_uuid).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Source '{source_id}' not found.")

    # Trigger async crawl task with case_id = investigation_id
    try:
        task = asyncio.create_task(
            run_crawl(
                source_id=str(source.id),
                case_id=investigation.investigation_id,
                triggered_by=current_user.id
            )
        )

        create_audit_log(
            db=db,
            action="INVESTIGATION_CRAWL_TRIGGERED",
            result="SUCCESS",
            user=current_user,
            resource_type="INVESTIGATION",
            resource_id=investigation.investigation_id,
            request=request,
            metadata={
                "source_id": str(source.id),
                "source_name": source.name
            }
        )

        db.commit()

        return {
            "message": f"Crawl triggered for source '{source.name}' in investigation {investigation_id}",
            "source_id": str(source.id),
            "status": "QUEUED"
        }

    except Exception as e:
        create_audit_log(
            db=db,
            action="INVESTIGATION_CRAWL_TRIGGERED",
            result="FAILURE",
            user=current_user,
            resource_type="INVESTIGATION",
            resource_id=investigation.investigation_id,
            request=request,
            metadata={"source_id": source_id, "error": str(e)[:100]}
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Crawl trigger failed: {str(e)[:100]}")

