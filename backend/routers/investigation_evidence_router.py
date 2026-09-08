"""
Investigation Evidence Router — Step 3

Provides endpoints for listing and promoting evidence within an investigation.

Evidence is stored in the existing DataProvenance table, extended with:
  - finding_id: FK to the InvestigationFinding that was promoted
  - raw_record_id: the source RawRecord's UUID as a string
  - promoted_by_id: FK to the User who performed the promotion
  - promoted_at: timestamp of promotion

Route registration:
  GET  /api/investigations/{investigation_id}/evidence
  POST /api/investigations/{investigation_id}/evidence/promote/{finding_id}

Authorization:
  - GET  : broad Permission.READ (any authenticated user)
  - POST : investigation modification access (v2)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from audit_service import create_audit_log
from database import get_db
from models import (
    DataProvenance,
    Investigation,
    InvestigationFinding,
    InvestigationFindingStatus,
    RawRecord,
    User,
)
from rbac import can_review_investigation_intelligence, require_permission, Permission
from routers.auth_router import get_current_user
from security import parse_uuid_safely

router = APIRouter(
    prefix="/api/investigations/{investigation_id}/evidence",
    tags=["Investigation Evidence"],
)


@router.get("")
def list_investigation_evidence(
    investigation_id: str,
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db),
):
    """
    List all evidence records promoted for this investigation.
    Reads the DataProvenance table scoped to investigation_id.
    """
    investigation = db.query(Investigation).filter(
        Investigation.investigation_id == investigation_id
    ).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    records = (
        db.query(DataProvenance)
        .filter(DataProvenance.investigation_id == investigation.investigation_id)
        .order_by(DataProvenance.collected_at.desc())
        .all()
    )

    return {
        "investigation_id": investigation_id,
        "total": len(records),
        "evidence": [
            {
                "id": r.id,
                "source_type": r.source_type,
                "source_name": r.source_name,
                "source_identifier": r.source_identifier,
                "source_url": r.source_url,
                "integrity_hash": r.integrity_hash,
                "finding_id": r.finding_id,
                "raw_record_id": r.raw_record_id,
                "promoted_by_id": r.promoted_by_id,
                "promoted_at": r.promoted_at.isoformat() if r.promoted_at else None,
                "collected_at": r.collected_at.isoformat(),
            }
            for r in records
        ],
    }


@router.post("/promote/{finding_id}", status_code=status.HTTP_201_CREATED)
def promote_finding_to_evidence(
    investigation_id: str,
    finding_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Promote a RELEVANT InvestigationFinding to a formal DataProvenance evidence record.

    Verification chain (Problem B compliance):
    1. Investigation must exist.
    2. User must have modification access (v2 RBAC).
    3. Finding must belong to this investigation (investigation_id FK match).
    4. Finding must be in RELEVANT status.
    5. The source RawRecord must be scoped to this investigation
       (RawRecord.case_id == investigation.investigation_id) — enforced on lookup.
    6. Idempotency: second attempt on the same finding_id returns HTTP 409.

    Audit: EVIDENCE_PROMOTED logged on success.
    """
    investigation = db.query(Investigation).filter(
        Investigation.investigation_id == investigation_id
    ).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )

    if not can_review_investigation_intelligence(current_user, investigation, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to promote evidence for this investigation.",
        )

    # Finding must belong to THIS investigation (integer PK FK match)
    finding = db.query(InvestigationFinding).filter(
        InvestigationFinding.id == finding_id,
        InvestigationFinding.investigation_id == investigation.id,
    ).first()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found for this investigation.",
        )

    if finding.review_status != InvestigationFindingStatus.RELEVANT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only findings marked RELEVANT can be promoted to evidence. "
                   f"Current status: {finding.review_status}",
        )

    # Idempotency guard: same finding → same evidence row
    existing = db.query(DataProvenance).filter(
        DataProvenance.finding_id == finding.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This finding has already been promoted to evidence.",
        )

    # Resolve the source RawRecord — verify it belongs to THIS investigation
    raw_record = None
    if finding.raw_record_id:
        record_uuid = parse_uuid_safely(finding.raw_record_id, field_name="raw_record_id")
        raw_record = db.query(RawRecord).filter(
            RawRecord.id == record_uuid,
            RawRecord.case_id == investigation.investigation_id,
        ).first()
        # If record exists but case_id doesn't match, it's a cross-investigation attempt
        if raw_record is None:
            # Try without case_id filter to give a more descriptive error
            orphan = db.query(RawRecord).filter(
                RawRecord.id == record_uuid
            ).first()
            if orphan and orphan.case_id != investigation.investigation_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The source record for this finding belongs to a different investigation.",
                )

    evidence = DataProvenance(
        source_type="Crawler Intelligence",
        source_name=(
            str(raw_record.source_id)
            if raw_record and raw_record.source_id
            else "Unknown Source"
        ),
        source_identifier=(
            str(raw_record.id) if raw_record else str(finding.raw_record_id)
        ),
        source_url=raw_record.url if raw_record else None,
        collection_method="Automated crawler collection, human-reviewed",
        investigation_id=investigation.investigation_id,
        original_record_reference=str(finding.raw_record_id),
        integrity_hash=raw_record.content_hash if raw_record else None,
        # Evidence promotion fields
        finding_id=finding.id,
        raw_record_id=str(finding.raw_record_id),
        promoted_by_id=current_user.id,
        promoted_at=datetime.now(timezone.utc),
    )
    db.add(evidence)

    create_audit_log(
        db=db,
        action="EVIDENCE_PROMOTED",
        result="SUCCESS",
        user=current_user,
        resource_type="INVESTIGATION",
        resource_id=investigation.investigation_id,
        request=request,
        metadata={
            "finding_id": finding.id,
            "raw_record_id": str(finding.raw_record_id),
            "evidence_integrity_hash": evidence.integrity_hash,
        },
    )

    db.commit()
    db.refresh(evidence)

    return {
        "message": "Finding promoted to evidence",
        "evidence_id": evidence.id,
        "investigation_id": investigation_id,
        "finding_id": finding.id,
        "integrity_hash": evidence.integrity_hash,
        "promoted_at": evidence.promoted_at.isoformat(),
    }
