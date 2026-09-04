from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from rbac import require_permission, Permission
from crawler.models.raw_record import RawRecord

router = APIRouter(prefix="/api/raw-records", tags=["Raw Records Output Contract"])


@router.get("")
def list_raw_records(
    status: Optional[str] = Query(default="pending_mapping"),
    case_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.READ)),
):
    query = db.query(RawRecord)
    if status:
        query = query.filter(RawRecord.status == status)
    if case_id:
        query = query.filter(RawRecord.case_id == case_id)

    total_count = query.count()
    records = query.order_by(RawRecord.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "status_filter": status,
        "items": [
            {
                "id": str(r.id),
                "run_id": str(r.run_id) if r.run_id else None,
                "source_id": str(r.source_id) if r.source_id else None,
                "case_id": r.case_id,
                "url": r.url,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
                "cleaned_text": r.cleaned_text,
                "content_hash": r.content_hash,
                "language": r.language,
                "matched_keywords": r.matched_keywords,
                "relevance_label": r.relevance_label,
                "relevance_confidence": float(r.relevance_confidence) if r.relevance_confidence else None,
                "relevance_reasoning": r.relevance_reasoning,
                "extracted_candidates": r.extracted_candidates,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }
