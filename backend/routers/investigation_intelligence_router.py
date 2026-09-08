import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from audit_service import create_audit_log
from database import get_db
from models import (
    Investigation,
    InvestigationFinding,
    InvestigationFindingStatus,
    RawRecord,
    User,
)
from rbac import can_review_investigation_intelligence, require_permission, Permission

from routers.auth_router import get_current_user
from security import get_client_ip, parse_uuid_safely
from semantic_search import SemanticIndex

router = APIRouter(prefix="/api/investigations/{investigation_id}/intelligence", tags=["Investigation Intelligence"])

# ============================================================================
# Pydantic Models
# ============================================================================

class ReviewIntelligenceRequest(BaseModel):
    review_status: str  # Must be one of: PENDING_REVIEW, RELEVANT, DISMISSED
    review_notes: Optional[str] = None

# ============================================================================
# Helper Function: Optimize N+1 Query
# ============================================================================

def get_findings_map(investigation_id: int, db: Session) -> dict:
    """
    Fetch all findings for an investigation in a single query.
    Returns a dictionary: {str(raw_record_id): InvestigationFinding}.
    Prevents N+1 queries in list views.
    """
    findings = db.query(InvestigationFinding).filter(
        InvestigationFinding.investigation_id == investigation_id
    ).all()
    return {str(f.raw_record_id): f for f in findings}

# ============================================================================
# Endpoints
# ============================================================================

@router.get("")
def list_investigation_intelligence(
    investigation_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    q: Optional[str] = Query(None, description="Optional exact or semantic intelligence search"),
    skip: int = Query(0),
    limit: int = Query(50),
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    List raw intelligence records scoped to this investigation.

    Each record includes its review status (from InvestigationFinding if exists).
    Records without findings have status=PENDING_REVIEW.

    Applies status filter at database level for accurate pagination.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    # Base query: RawRecords for this case
    query = db.query(RawRecord).filter(RawRecord.case_id == investigation.investigation_id)
    semantic_scores = {}
    query_text = (q or "").strip()
    if query_text:
        try:
            semantic_matches = SemanticIndex().search(query_text, {"raw_record"}, investigation.investigation_id, 100)
        except Exception:
            semantic_matches = []
        semantic_scores = {match["source_id"]: match["score"] for match in semantic_matches}
        exact_filter = or_(
            RawRecord.url.ilike(f"%{query_text}%"),
            RawRecord.raw_text.ilike(f"%{query_text}%"),
            RawRecord.cleaned_text.ilike(f"%{query_text}%"),
            RawRecord.relevance_reasoning.ilike(f"%{query_text}%"),
        )
        if semantic_scores:
            semantic_record_ids = [uuid.UUID(record_id) for record_id in semantic_scores]
            query = query.filter(or_(exact_filter, RawRecord.id.in_(semantic_record_ids)))
        else:
            query = query.filter(exact_filter)

    # If filtering by status, JOIN with InvestigationFinding
    if status_filter:
        if status_filter not in InvestigationFindingStatus.all_values():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status filter. Must be one of: {InvestigationFindingStatus.all_values()}")

        if status_filter == InvestigationFindingStatus.PENDING_REVIEW:
            query = query.outerjoin(
                InvestigationFinding,
                (InvestigationFinding.raw_record_id == RawRecord.id) &
                (InvestigationFinding.investigation_id == investigation.id)
            ).filter(
                or_(
                    InvestigationFinding.id == None,
                    InvestigationFinding.review_status == InvestigationFindingStatus.PENDING_REVIEW
                )
            )
        else:
            query = query.join(
                InvestigationFinding,
                (InvestigationFinding.raw_record_id == RawRecord.id) &
                (InvestigationFinding.investigation_id == investigation.id)
            ).filter(InvestigationFinding.review_status == status_filter)

    total = query.count()
    raw_records = query.order_by(RawRecord.fetched_at.desc()).offset(skip).limit(limit).all()
    if semantic_scores:
        raw_records.sort(key=lambda record: semantic_scores.get(str(record.id), 0), reverse=True)

    # Fetch all findings for this investigation ONCE
    findings_map = get_findings_map(investigation.id, db)

    results = []
    for record in raw_records:
        rec_id_str = str(record.id)
        finding = findings_map.get(rec_id_str)
        review_status = finding.review_status if finding else InvestigationFindingStatus.PENDING_REVIEW

        result = {
            "id": rec_id_str,
            "raw_record_id": rec_id_str,
            "source_url": record.url,
            "fetched_at": record.fetched_at.isoformat() if record.fetched_at else None,
            "matched_keywords": getattr(record, 'matched_keywords', None),
            "language": getattr(record, 'language', None),
            "relevance_label": getattr(record, 'relevance_label', None),
            "relevance_confidence": getattr(record, 'relevance_confidence', None),
            "extracted_candidates": json.dumps(record.extracted_candidates) if isinstance(getattr(record, 'extracted_candidates', None), (dict, list)) else getattr(record, 'extracted_candidates', None),
            "review_status": review_status,
            "review_notes": finding.review_notes if finding else None,
            "reviewed_by_email": finding.reviewed_by.email if (finding and finding.reviewed_by) else None,
            "reviewed_at": finding.reviewed_at.isoformat() if (finding and finding.reviewed_at) else None
        }
        if query_text and rec_id_str in semantic_scores:
            result["match_reason"] = f"Semantic similarity ({int(semantic_scores[rec_id_str] * 100)}%)"
            result["semantic_score"] = semantic_scores[rec_id_str]
        results.append(result)

    return {
        "investigation_id": investigation_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "query": query_text or None,
        "records": results
    }


@router.get("/{raw_record_id}")
def get_intelligence_detail(
    investigation_id: str,
    raw_record_id: str,
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    Get full details of a single raw intelligence record + its review status.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    record_uuid = parse_uuid_safely(raw_record_id, field_name="raw_record_id")
    record = db.query(RawRecord).filter(
        RawRecord.id == record_uuid,
        RawRecord.case_id == investigation.investigation_id
    ).first()

    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Record not found for this investigation.")

    finding = db.query(InvestigationFinding).filter(
        InvestigationFinding.investigation_id == investigation.id,
        InvestigationFinding.raw_record_id == str(record.id)
    ).first()

    return {
        "id": str(record.id),
        "raw_record_id": str(record.id),
        "source_id": str(record.source_id) if record.source_id else None,
        "url": record.url,
        "raw_text_excerpt": record.raw_text[:500] if getattr(record, 'raw_text', None) else None,
        "cleaned_text": getattr(record, 'cleaned_text', None),
        "language": getattr(record, 'language', None),
        "fetched_at": record.fetched_at.isoformat() if record.fetched_at else None,
        "matched_keywords": getattr(record, 'matched_keywords', None),
        "relevance_label": getattr(record, 'relevance_label', None),
        "relevance_confidence": getattr(record, 'relevance_confidence', None),
        "relevance_reasoning": getattr(record, 'relevance_reasoning', None),
        "extracted_candidates": getattr(record, 'extracted_candidates', None),
        "content_hash": getattr(record, 'content_hash', None),
        "review_status": finding.review_status if finding else InvestigationFindingStatus.PENDING_REVIEW,
        "review_notes": finding.review_notes if finding else None,
        "reviewed_by_id": finding.reviewed_by_id if finding else None,
        "reviewed_by_email": finding.reviewed_by.email if (finding and finding.reviewed_by) else None,
        "reviewed_at": finding.reviewed_at.isoformat() if (finding and finding.reviewed_at) else None
    }


@router.post("/{raw_record_id}/review")
def review_intelligence(
    investigation_id: str,
    raw_record_id: str,
    req: ReviewIntelligenceRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Review a raw intelligence record: mark as RELEVANT, DISMISSED, or PENDING_REVIEW.

    Creates or updates InvestigationFinding (upsert).
    Requires investigation modification access.
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    if not can_review_investigation_intelligence(current_user, investigation, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    record_uuid = parse_uuid_safely(raw_record_id, field_name="raw_record_id")
    record = db.query(RawRecord).filter(
        RawRecord.id == record_uuid,
        RawRecord.case_id == investigation.investigation_id
    ).first()

    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Record not found for this investigation.")

    # Validate review_status
    if req.review_status not in InvestigationFindingStatus.all_values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid review_status. Must be one of: {', '.join(InvestigationFindingStatus.all_values())}"
        )

    # Upsert finding
    finding = db.query(InvestigationFinding).filter(
        InvestigationFinding.investigation_id == investigation.id,
        InvestigationFinding.raw_record_id == str(record.id)
    ).first()

    if finding:
        finding.review_status = req.review_status
        finding.review_notes = req.review_notes
        finding.reviewed_by_id = current_user.id
        finding.reviewed_at = datetime.now(timezone.utc)
        finding.updated_at = datetime.now(timezone.utc)
        action_type = "INVESTIGATION_INTELLIGENCE_REVIEWED_UPDATE"
    else:
        finding = InvestigationFinding(
            investigation_id=investigation.id,
            raw_record_id=str(record.id),
            review_status=req.review_status,
            review_notes=req.review_notes,
            reviewed_by_id=current_user.id,
            reviewed_at=datetime.now(timezone.utc)
        )
        db.add(finding)
        action_type = "INVESTIGATION_INTELLIGENCE_REVIEWED"

    create_audit_log(
        db=db,
        action=action_type,
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "raw_record_id": str(record.id),
            "review_status": req.review_status,
            "review_notes": req.review_notes[:100] if req.review_notes else None
        }
    )

    db.commit()
    db.refresh(finding)

    return {
        "message": f"Intelligence reviewed successfully",
        "finding_id": finding.id,
        "raw_record_id": str(record.id),
        "review_status": finding.review_status
    }


@router.get("/findings/list")
def list_investigation_findings(
    investigation_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0),
    limit: int = Query(50),
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db)
):
    """
    List reviewed findings (records with explicit review decisions).
    """
    investigation = db.query(Investigation).filter(Investigation.investigation_id == investigation_id).first()
    if not investigation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Investigation '{investigation_id}' not found.")

    query = db.query(InvestigationFinding).filter(InvestigationFinding.investigation_id == investigation.id)

    if status_filter:
        if status_filter not in InvestigationFindingStatus.all_values():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter.")
        query = query.filter(InvestigationFinding.review_status == status_filter)

    total = query.count()
    findings = query.order_by(InvestigationFinding.reviewed_at.desc()).offset(skip).limit(limit).all()

    return {
        "investigation_id": investigation_id,
        "total": total,
        "skip": skip,
        "limit": limit,
        "findings": [
            {
                "id": f.id,
                "raw_record_id": str(f.raw_record_id),
                "url": f.raw_record.url if hasattr(f, 'raw_record') and f.raw_record else None,
                "review_status": f.review_status,
                "review_notes": f.review_notes,
                "reviewed_by_email": f.reviewed_by.email if f.reviewed_by else None,
                "reviewed_at": f.reviewed_at.isoformat()
            }
            for f in findings
        ]
    }

