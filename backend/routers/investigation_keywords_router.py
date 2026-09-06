import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from audit_service import create_audit_log
from database import get_db
from models import CaseKeyword, Investigation, Keyword, User
from rbac import can_manage_investigation_keywords, require_permission, Permission

from routers.auth_router import get_current_user
from routers.reauth_router import require_recent_reauth
from security import get_client_ip

router = APIRouter(prefix="/api/investigations/{investigation_id}/keywords", tags=["Investigation Keywords"])

# ============================================================================
# Pydantic Models
# ============================================================================

class AddKeywordRequest(BaseModel):
    keyword_id: str  # String representation of Keyword UUID or ID

# ============================================================================
# Endpoints
# ============================================================================

@router.get("")
def list_investigation_keywords(
    investigation_id: str,
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    List active case-specific keywords for an investigation.
    All authenticated users can view.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    case_keywords = db.query(CaseKeyword).filter(
        CaseKeyword.case_id == investigation.investigation_id,
        CaseKeyword.is_active == True
    ).all()

    # Enrich response with Keyword details
    results = []
    for ck in case_keywords:
        kw_uuid = uuid.UUID(str(ck.keyword_id)) if isinstance(ck.keyword_id, str) and "-" in str(ck.keyword_id) else ck.keyword_id
        keyword = db.query(Keyword).filter(Keyword.id == kw_uuid).first() if kw_uuid else None
        results.append({
            "id": str(ck.id),
            "keyword_id": str(ck.keyword_id),
            "keyword_text": keyword.term if keyword else "Unknown",
            "language": keyword.language if keyword else "en",
            "category": getattr(keyword, 'category', None) if keyword else None,
            "added_by_id": ck.added_by,
            "added_at": ck.added_at.isoformat() if hasattr(ck, 'added_at') and ck.added_at else None
        })

    return {
        "investigation_id": investigation_id,
        "keywords": results
    }


@router.post("")
def add_investigation_keyword(
    investigation_id: str,
    req: AddKeywordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    """
    Add a global keyword to an investigation's case-specific keywords.
    Requires investigation modification access + re-authentication.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    if not can_manage_investigation_keywords(current_user, investigation, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    kw_uuid = uuid.UUID(req.keyword_id) if isinstance(req.keyword_id, str) and "-" in req.keyword_id else req.keyword_id
    keyword = db.query(Keyword).filter(Keyword.id == kw_uuid).first()
    if not keyword:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found.")

    # Check if already added (active)
    existing = db.query(CaseKeyword).filter(
        CaseKeyword.case_id == investigation.investigation_id,
        CaseKeyword.keyword_id == keyword.id,
        CaseKeyword.is_active == True
    ).first()

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Keyword '{keyword.term}' is already added to this investigation.")

    # Add or reactivate
    case_keyword = db.query(CaseKeyword).filter(
        CaseKeyword.case_id == investigation.investigation_id,
        CaseKeyword.keyword_id == keyword.id
    ).first()

    if case_keyword:
        case_keyword.is_active = True
    else:
        case_keyword = CaseKeyword(
            case_id=investigation.investigation_id,
            keyword_id=keyword.id,
            added_by=current_user.id,
            is_active=True
        )
        db.add(case_keyword)

    create_audit_log(
        db=db,
        action="INVESTIGATION_KEYWORD_ADDED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={"keyword_id": str(keyword.id), "keyword_text": keyword.term}
    )

    db.commit()
    db.refresh(case_keyword)

    return {
        "message": f"Keyword '{keyword.term}' added to investigation {investigation_id}",
        "keyword_id": str(keyword.id)
    }


@router.delete("/{keyword_id}")
def remove_investigation_keyword(
    investigation_id: str,
    keyword_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    reauth_user: User = Depends(require_recent_reauth),
    db: Session = Depends(get_db)
):
    """
    Remove (deactivate) a keyword from an investigation.
    Does not delete the global Keyword; just deactivates for this case.
    Requires investigation modification access + re-authentication.

    Uses path parameter {keyword_id}.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    if not can_manage_investigation_keywords(current_user, investigation, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    kw_uuid = uuid.UUID(keyword_id) if isinstance(keyword_id, str) and "-" in keyword_id else keyword_id

    case_keyword = db.query(CaseKeyword).filter(
        CaseKeyword.case_id == investigation.investigation_id,
        CaseKeyword.keyword_id == kw_uuid,
        CaseKeyword.is_active == True
    ).first()

    if not case_keyword:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword is not active for this investigation.")

    keyword = db.query(Keyword).filter(Keyword.id == kw_uuid).first()
    keyword_text = keyword.term if keyword else "Unknown"
    case_keyword.is_active = False

    create_audit_log(
        db=db,
        action="INVESTIGATION_KEYWORD_REMOVED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={"keyword_id": keyword_id, "keyword_text": keyword_text}
    )

    db.commit()

    return {"message": f"Keyword '{keyword_text}' removed successfully", "keyword_id": keyword_id}

