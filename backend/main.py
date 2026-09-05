from fastapi import FastAPI, Request, Depends
import asyncio
from crawler.orchestration.scheduler import CrawlerScheduler
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from datetime import datetime
import json
import os

from database import init_db, get_db
from models import User, Suspect, CryptoWallet, DarknetListing, TelegramMessage, TelegramChannel, NetworkTrafficFlow
from routers.auth_router import router as auth_router, get_current_user
from routers.admin_router import router as admin_router
from routers.reauth_router import router as reauth_router
from routers.delegation_router import router as delegation_router
from routers.audit_router import router as audit_router
from routers.evidence_provenance_router import router as evidence_provenance_router
from routers.search_router import router as search_router
from sqlalchemy.orm import Session
from datetime import datetime, timezone

import asyncio
from pipelines.ingest_ai_router import start_background_ingestion_task, INGESTION_STATUS
from crawler.api.routers.sources import router as sources_router
from crawler.api.routers.keywords import router as keywords_router
from crawler.api.routers.raw_records import router as raw_records_router
from crawler.api.routers.activity import router as activity_router

from crawler.api.routers.sources import router as sources_router
from crawler.api.routers.keywords import router as keywords_router
from crawler.api.routers.raw_records import router as raw_records_router
from crawler.api.routers.activity import router as activity_router

crawler_scheduler = CrawlerScheduler()
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(start_background_ingestion_task())
    yield

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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
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

# Include Routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(reauth_router)
app.include_router(delegation_router)
app.include_router(audit_router)
app.include_router(evidence_provenance_router)
app.include_router(search_router)
app.include_router(sources_router)
app.include_router(keywords_router)
app.include_router(raw_records_router)
app.include_router(activity_router)

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
    total_suspects = db.query(Suspect).count()
    critical_alerts = db.query(Suspect).filter(Suspect.risk_score >= 80).count()
    total_wallets = db.query(CryptoWallet).count()
    total_listings = db.query(DarknetListing).count()
    total_messages = db.query(TelegramMessage).count()
    total_channels = db.query(TelegramChannel).count()
    total_flows = db.query(NetworkTrafficFlow).count()

    return {
        "active_investigations": total_suspects,
        "critical_alerts": critical_alerts,
        "sources_monitored": 4,
        "total_suspects": total_suspects,
        "total_wallets": total_wallets,
        "total_listings": total_listings,
        "total_telegram_messages": total_messages,
        "total_telegram_channels": total_channels,
        "total_network_traffic_flows": total_flows,
        "last_update": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/alerts/suspicious")
def get_suspicious_activity(current_user: User = Depends(get_current_user)):
    db = load_db()
    return db.get("suspicious_activity", [])

@app.get("/api/reports")
def get_reports(current_user: User = Depends(get_current_user)):
    db = load_db()
    return db.get("reports", [])

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