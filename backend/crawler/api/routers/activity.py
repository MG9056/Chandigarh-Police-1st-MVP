from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User
from rbac import require_permission, Permission
from crawler.models.crawler_run import CrawlerRun
from crawler.models.source import Source

router = APIRouter(prefix="/api/crawler/activity", tags=["Crawler Activity Feed"])


@router.get("")
def get_crawler_activity(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    source_id: Optional[str] = Query(default=None),
    case_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.READ)),
):
    query = db.query(CrawlerRun)

    if source_id:
        query = query.filter(CrawlerRun.source_id == source_id)
    if case_id:
        query = query.filter(CrawlerRun.case_id == case_id)

    total_count = query.count()
    offset = (page - 1) * page_size

    runs = query.order_by(CrawlerRun.started_at.desc()).offset(offset).limit(page_size).all()

    items = []
    for r in runs:
        source_name = "Unknown Source"
        if r.source_id:
            src = db.query(Source).filter(Source.id == r.source_id).first()
            if src:
                source_name = src.name

        items.append({
            "id": str(r.id),
            "source_id": str(r.source_id) if r.source_id else None,
            "source_name": source_name,
            "case_id": r.case_id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "urls_attempted": r.urls_attempted,
            "urls_skipped_robots": r.urls_skipped_robots,
            "records_produced": r.records_produced,
            "records_relevant": r.records_relevant,
            "errors_count": r.errors_count,
            "error_summary": r.error_summary,
            "triggered_by": r.triggered_by,
        })

    return {
        "page": page,
        "page_size": page_size,
        "total": total_count,
        "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 1,
        "items": items,
    }
