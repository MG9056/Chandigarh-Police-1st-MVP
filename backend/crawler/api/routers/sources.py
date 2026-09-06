import asyncio
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User
from rbac import require_permission, Permission
from crawler.models.source import Source
from crawler.models.crawler_run import CrawlerRun
from crawler.orchestration.flows import run_crawl


router = APIRouter(prefix="/api/sources", tags=["Crawler Sources"])


SUPPORTED_SOURCE_TYPES = {
    "GOOGLE_SEARCH_DISCOVERY",
    "DIRECT_SEED",
    "BITCOIN_CHAIN",
    "TELEGRAM_PUBLIC",
    "TOR_STUB",
    "POLICE_API",
}


class SourceCreate(BaseModel):
    name: str
    source_type: str
    config: Dict[str, Any] = {}

    poll_interval_minutes: int = 60
    poll_interval_seconds: int = 60

    crawl_delay_seconds: float = 1.0
    transport_type: str = "direct"


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    poll_interval_seconds: Optional[int] = None
    crawl_delay_seconds: Optional[float] = None
    is_active: Optional[bool] = None
    transport_type: Optional[str] = None


@router.get("")
def list_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.READ)),
):
    sources = db.query(Source).all()
    results = []

    for s in sources:
        last_run = (
            db.query(CrawlerRun)
            .filter(CrawlerRun.source_id == s.id)
            .order_by(CrawlerRun.started_at.desc())
            .first()
        )

        results.append({
            "id": str(s.id),
            "name": s.name,
            "source_type": s.source_type,
            "config": s.config,
            "poll_interval_seconds": s.poll_interval_seconds,
            "crawl_delay_seconds": float(s.crawl_delay_seconds or 1.0),
            "is_active": s.is_active,
            "transport_type": s.transport_type,
            "created_at": (
                s.created_at.isoformat()
                if s.created_at
                else None
            ),
            "last_run": {
                "id": str(last_run.id) if last_run else None,
                "status": (
                    last_run.status
                    if last_run
                    else "NEVER_RUN"
                ),
                "started_at": (
                    last_run.started_at.isoformat()
                    if last_run and last_run.started_at
                    else None
                ),
                "records_produced": (
                    last_run.records_produced
                    if last_run
                    else 0
                ),
            } if last_run else None,
        })

    return results


@router.post("")
def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
):
    source_type = payload.source_type.upper()

    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported source type: {source_type}",
        )

    if source_type == "POLICE_API":
        api_url = payload.config.get("url")

        if not api_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Police API source requires a URL.",
            )

        method = payload.config.get(
            "method",
            "GET",
        ).upper()

        if method != "GET":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Police API currently supports only GET requests.",
            )

        payload.config["method"] = "GET"

    source = Source(
        id=uuid.uuid4(),
        name=payload.name,
        source_type=source_type,
        config=payload.config,
        poll_interval_seconds=payload.poll_interval_seconds,
        crawl_delay_seconds=payload.crawl_delay_seconds,
        transport_type=payload.transport_type,
        created_by=current_user.id,
    )

    db.add(source)
    db.commit()
    db.refresh(source)

    return {
        "id": str(source.id),
        "name": source.name,
        "source_type": source.source_type,
    }


@router.patch("/{source_id}")
def update_source(
    source_id: str,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
):
    source_uuid = (
        uuid.UUID(source_id)
        if isinstance(source_id, str)
        else source_id
    )

    source = (
        db.query(Source)
        .filter(Source.id == source_uuid)
        .first()
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    if payload.name is not None:
        source.name = payload.name

    if payload.config is not None:
        source.config = payload.config

    if payload.poll_interval_seconds is not None:
        source.poll_interval_seconds = payload.poll_interval_seconds

    if payload.crawl_delay_seconds is not None:
        source.crawl_delay_seconds = payload.crawl_delay_seconds

    if payload.is_active is not None:
        source.is_active = payload.is_active

    if payload.transport_type is not None:
        source.transport_type = payload.transport_type

    db.commit()

    return {
        "message": "Source updated successfully",
        "id": str(source.id),
    }


@router.post("/{source_id}/trigger")
async def trigger_source_run(
    source_id: str,
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
):
    source_uuid = (
        uuid.UUID(source_id)
        if isinstance(source_id, str)
        else source_id
    )

    source = (
        db.query(Source)
        .filter(Source.id == source_uuid)
        .first()
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    # Run Now reactivates the source so it can be crawled again
    source.is_active = True
    db.commit()

    asyncio.create_task(
        run_crawl(
            source_id=source.id,
            case_id=case_id,
            triggered_by=current_user.id,
        )
    )

    return {
        "message": f"Crawl run triggered for source '{source.name}'",
        "source_id": str(source.id),
        "case_id": case_id,
        "triggered_by": current_user.id,
    }


@router.post("/{source_id}/stop")
def stop_source_run(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
):
    source_uuid = (
        uuid.UUID(source_id)
        if isinstance(source_id, str)
        else source_id
    )

    source = (
        db.query(Source)
        .filter(Source.id == source_uuid)
        .first()
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    source.is_active = False

    # Mark active runs as STOPPED
    active_runs = (
        db.query(CrawlerRun)
        .filter(
            CrawlerRun.source_id == source_uuid,
            CrawlerRun.status == "RUNNING",
        )
        .all()
    )

    for r in active_runs:
        r.status = "STOPPED"
        r.finished_at = datetime.now(timezone.utc)
        r.error_summary = "Crawl stopped by operator."

    db.commit()


    # Trigger B: final catch-up sync so DB reflects any CSVs written
    # during this crawl session before the operator navigates away.
    try:
        from db_sync import run_dataset_sync
        import logging
        _log = logging.getLogger("sources_router")
        _log.info(
            "[sources_router] Crawl stopped for source %s — triggering final DB sync.",
            source_id,
        )
        run_dataset_sync(db, reason="crawler_stopped")
    except Exception as sync_exc:
        import logging
        logging.getLogger("sources_router").error(
            "[sources_router] Post-stop DB sync failed (non-fatal): %s", sync_exc, exc_info=True
        )

    return {"message": f"Source '{source.name}' stopped and deactivated.", "source_id": str(source.id)}


@router.delete("/{source_id}")
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_DATA_SOURCES)),
):
    source_uuid = (
        uuid.UUID(source_id)
        if isinstance(source_id, str)
        else source_id
    )

    source = (
        db.query(Source)
        .filter(Source.id == source_uuid)
        .first()
    )

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    # Delete associated crawler runs
    db.query(CrawlerRun).filter(
        CrawlerRun.source_id == source_uuid
    ).delete(
        synchronize_session=False
    )

    db.delete(source)
    db.commit()

    return {
        "message": (
            f"Source '{source.name}' deleted successfully"
        ),
        "id": str(source_id),
    }