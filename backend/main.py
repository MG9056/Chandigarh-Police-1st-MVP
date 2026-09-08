import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os


from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

load_dotenv()

from database import init_db, get_db
from models import (
    User,
    Investigation,
    Report,
    Suspect,
    CryptoWallet,
    DarknetListing,
    TelegramMessage,
    TelegramChannel,
    NetworkTrafficFlow,
)
from crawler.orchestration.scheduler import CrawlerScheduler
from pipelines.ingest_ai_router import start_background_ingestion_task, INGESTION_STATUS
from crawler.models.source import Source
from routers.auth_router import router as auth_router, get_current_user
from rbac import Permission, require_permission
from routers.admin_router import router as admin_router
from routers.reauth_router import router as reauth_router
from routers.delegation_router import router as delegation_router
from routers.audit_router import router as audit_router
from routers.evidence_provenance_router import router as evidence_provenance_router
from routers.search_router import router as search_router
from crawler_to_dataset_updater import start_crawler_dataset_updater
from routers.investigation_router import router as investigation_router
from routers.alerts_router import router as alerts_router
from routers.investigation_sources_router import router as investigation_sources_router
from routers.investigation_intelligence_router import router as investigation_intelligence_router
from routers.investigation_keywords_router import router as investigation_keywords_router

from routers.investigation_evidence_router import router as investigation_evidence_router
from routers.investigation_alerts_router import router as investigation_alerts_router
from routers.investigation_alerts_router import global_alerts_router
from routers.reports_router import router as reports_router
from routers.ai_router import router as ai_router
from crawler.api.routers.sources import router as sources_router
from crawler.api.routers.keywords import router as keywords_router
from crawler.api.routers.raw_records import router as raw_records_router
from crawler.api.routers.activity import router as activity_router



crawler_scheduler = CrawlerScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    init_db()


    asyncio.create_task(start_crawler_dataset_updater(poll_interval_seconds=60))

    scheduler_task = asyncio.create_task(
        crawler_scheduler.start()
    )

    try:
        yield
    finally:
        crawler_scheduler.stop()
        scheduler_task.cancel()

        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="DarKnight API",
    description="Security-enforced API for Chandigarh Police Intelligence Platform",
    lifespan=lifespan
)

# Enable CORS with credentials for cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000","https://darknight-tau.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Security Headers Middleware (PRD Section S-12)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:;"
    return response

# Include Routers — Security & Investigation
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(reauth_router)
app.include_router(delegation_router)
app.include_router(audit_router)
app.include_router(evidence_provenance_router)
app.include_router(search_router)
app.include_router(investigation_router)
app.include_router(alerts_router)
app.include_router(investigation_sources_router)
app.include_router(investigation_intelligence_router)
app.include_router(investigation_keywords_router)
app.include_router(investigation_evidence_router)
app.include_router(investigation_alerts_router)
app.include_router(global_alerts_router)
app.include_router(reports_router)
app.include_router(ai_router)


# Include Routers — Crawler subsystem
app.include_router(sources_router)
app.include_router(keywords_router)
app.include_router(raw_records_router)
app.include_router(activity_router)



@app.get("/api/global/entities", tags=["Global Intelligence"])
def get_global_entities(
    limit_records: int = 500,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Global entity co-occurrence graph — all investigations, all RawRecords.
    CO_OCCURRENCE edges are observational only; not confirmed relationships.
    Feeds the global Network view (separate from the Elliptic++/Dread demo dataset).
    """
    from crawler.pipeline.entity_aggregation import aggregate_entities
    return aggregate_entities(db, case_id=None, limit_records=limit_records)


@app.get("/api/global/geography", tags=["Global Intelligence"])
def get_global_geography(
    limit_records: int = 500,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Global geographic hotspot map — all investigations, all RawRecords.
    Resolves LOCATION entities against the India gazetteer.
    Feeds the global Geography view (separate from the geo_signals/Dread demo dataset).
    """
    from crawler.pipeline.entity_aggregation import aggregate_geography
    return aggregate_geography(db, case_id=None, limit_records=limit_records)


def load_db():
    db_path = os.path.join(os.path.dirname(__file__), "mock_db.json")
    if os.path.exists(db_path):
        with open(db_path, "r") as f:
            return json.load(f)
    return {}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to DarKnight API"}

@app.get("/api/ingestion-status")
def get_ingestion_status(current_user: User = Depends(get_current_user)):
    from pipelines.ingest_ai_router import INGESTION_STATUS
    return INGESTION_STATUS

@app.get("/api/dashboard/summary")
def get_dashboard_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    active_investigations = db.query(Investigation).filter(
        Investigation.status.in_(["OPEN", "ACTIVE"])
    ).count()
    total_suspects = db.query(Suspect).count()
    critical_alerts = db.query(Suspect).filter(Suspect.risk_score >= 80).count()
    total_wallets = db.query(CryptoWallet).count()
    total_listings = db.query(DarknetListing).count()
    total_messages = db.query(TelegramMessage).count()
    total_channels = db.query(TelegramChannel).count()
    total_flows = db.query(NetworkTrafficFlow).count()
    total_sources = db.query(Source).count()

    return {
        "active_investigations": active_investigations,
        "critical_alerts": critical_alerts,
        "sources_monitored": total_sources,
        "total_suspects": total_suspects,
        "total_wallets": total_wallets,
        "total_listings": total_listings,
        "total_telegram_messages": total_messages,
        "total_telegram_channels": total_channels,
        "total_network_traffic_flows": total_flows,
        "last_update": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/data-sources")
@app.get("/api/data-collection/status")
def get_data_sources(current_user: User = Depends(get_current_user)):
    db = load_db()
    return db.get("data_sources", [])

# /api/alerts — now served by routers/alerts_router.py (DB-backed)

@app.get("/api/network/data")
def get_network_data(current_user: User = Depends(get_current_user)):
    db = load_db()
    return db.get("network_data", {"nodes": [], "links": []})

@app.get("/api/search")
def search_entities(q: str = "", current_user: User = Depends(get_current_user)):
    db = load_db()
    results = db.get("search_entities", [])
    if q:
        results = [r for r in results if q.lower() in r["identifier"].lower()]
    return {"results": results}

# /api/alerts/suspicious — now served by routers/alerts_router.py (DB-backed)

@app.get("/api/reports", tags=["Global Reports"])
def get_global_reports(
    current_user: User = Depends(require_permission(Permission.READ)),
    db: Session = Depends(get_db),
):
    """
    List all generated investigation reports for the global
    Reports & Evidence dashboard.

    Returns report data together with case metadata and
    assigned investigators so the frontend does not need
    to make one request per investigation.
    """

    reports = (
        db.query(Report)
        .order_by(Report.created_at.desc())
        .all()
    )

    result = []

    for report in reports:
        investigation = report.investigation

        if not investigation:
            continue

        # Active assigned investigators only
        assigned_officers = []

        for assignment in investigation.assignments or []:
            if assignment.removed_at is not None:
                continue

            if assignment.assigned_to:
                assigned_officers.append({
                    "id": assignment.assigned_to.id,
                    "name": assignment.assigned_to.full_name,
                    "email": assignment.assigned_to.email,
                    "badge_number": assignment.assigned_to.badge_number,
                    "unit": assignment.assigned_to.unit,
                })

        # Include lead investigator separately if present
        lead_investigator = None

        if investigation.lead_investigator:
            lead_investigator = {
                "id": investigation.lead_investigator.id,
                "name": investigation.lead_investigator.full_name,
                "email": investigation.lead_investigator.email,
                "badge_number": investigation.lead_investigator.badge_number,
                "unit": investigation.lead_investigator.unit,
            }

        structured_data = report.structured_data or {}

        result.append({
            "id": report.id,
            "report_id": report.report_id,

            # Report information
            "title": report.title,
            "status": report.status,
            "model_used": report.model_used,
            "created_at": (
                report.created_at.isoformat()
                if report.created_at
                else None
            ),

            # AI-generated summary
            "summary": structured_data.get(
                "executive_summary",
                ""
            ),

            # Case information
            "investigation_id": investigation.investigation_id,
            "case_title": investigation.title,
            "case_type": investigation.case_type,
            "case_status": investigation.status,
            "priority": investigation.priority,
            "unit": investigation.unit,
            "description": investigation.description,

            # Officers
            "lead_investigator": lead_investigator,
            "assigned_officers": assigned_officers,

            # Evidence
            "evidence_count": len(
                report.evidence_references or {}
            ),
        })

    return {
        "total": len(result),
        "reports": result,
    }

@app.get("/api/network/synthetic")
def get_synthetic_network_data(current_user: User = Depends(get_current_user)):
    from graph_adapter import build_network_data
    return build_network_data()

@app.get("/api/network/real")
def get_real_network_data(refresh: bool = False, current_user: User = Depends(get_current_user)):
    from real_data.graph_builder import get_cached_or_build
    from graph_adapter import build_network_data
    try:
        data = get_cached_or_build(force=refresh)
        if data and len(data.get("nodes", [])) > 0:
            return data
        return build_network_data()
    except Exception as e:
        return build_network_data()

@app.get("/api/geo/activity")
def get_geo_activity(refresh: bool = False, current_user: User = Depends(get_current_user)):
    from real_data.geo_signals import get_cached_or_build_geo
    try:
        data = get_cached_or_build_geo(force=refresh)
        if data and len(data.get("places", [])) > 0:
            return data
        return {
            "places": [
                {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777, "count": 240},
                {"name": "Delhi", "lat": 28.6139, "lon": 77.2090, "count": 180},
                {"name": "Chandigarh", "lat": 30.7333, "lon": 76.7794, "count": 150},
                {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946, "count": 110},
                {"name": "Goa", "lat": 15.2993, "lon": 74.1240, "count": 95}
            ],
            "total_mentions": 775,
            "distinct_places_mentioned": 5,
            "india_board_posts": 42
        }
    except Exception as e:
        return {
            "places": [
                {"name": "Mumbai", "lat": 19.0760, "lon": 72.8777, "count": 240},
                {"name": "Delhi", "lat": 28.6139, "lon": 77.2090, "count": 180},
                {"name": "Chandigarh", "lat": 30.7333, "lon": 76.7794, "count": 150},
                {"name": "Bengaluru", "lat": 12.9716, "lon": 77.5946, "count": 110},
                {"name": "Goa", "lat": 15.2993, "lon": 74.1240, "count": 95}
            ],
            "total_mentions": 775,
            "distinct_places_mentioned": 5,
            "india_board_posts": 42
        }