from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime
import json
import os

from database import init_db
from models import User
from routers.auth_router import router as auth_router, get_current_user
from routers.admin_router import router as admin_router
from routers.reauth_router import router as reauth_router
from routers.delegation_router import router as delegation_router
from routers.audit_router import router as audit_router
from routers.evidence_provenance_router import router as evidence_provenance_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

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

def load_db():
    db_path = os.path.join(os.path.dirname(__file__), "mock_db.json")
    if os.path.exists(db_path):
        with open(db_path, "r") as f:
            return json.load(f)
    return {}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to DarKnight API"}

@app.get("/api/dashboard/summary")
def get_dashboard_summary(current_user: User = Depends(get_current_user)):
    db = load_db()
    summary = db.get("dashboard_summary", {})
    summary["last_update"] = datetime.now().isoformat()
    return summary

@app.get("/api/data-sources")
@app.get("/api/data-collection/status")
def get_data_sources(current_user: User = Depends(get_current_user)):
    db = load_db()
    return db.get("data_sources", [])

@app.get("/api/alerts")
def get_alerts(current_user: User = Depends(get_current_user)):
    db = load_db()
    return db.get("alerts", [])

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
    try:
        return get_cached_or_build(force=refresh)
    except FileNotFoundError as e:
        return {
            "nodes": [], "links": [],
            "error": f"Real data not found: {e}. Drop Elliptic++ CSVs into "
                     "backend/real_data_files/elliptic/ and Dread parquet files into "
                     "backend/real_data_files/dread/, then retry.",
        }

@app.get("/api/geo/activity")
def get_geo_activity(refresh: bool = False, current_user: User = Depends(get_current_user)):
    from real_data.geo_signals import get_cached_or_build_geo
    try:
        return get_cached_or_build_geo(force=refresh)
    except FileNotFoundError as e:
        return {"places": [], "total_mentions": 0, "distinct_places_mentioned": 0, "india_board_posts": 0, "error": f"Real data not found: {e}"}