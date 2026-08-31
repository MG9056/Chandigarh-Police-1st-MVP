from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import json
import os

app = FastAPI(title="DarKnight MVP API", description="Dummy API for DarKnight Dashboard")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
def get_dashboard_summary():
    db = load_db()
    summary = db.get("dashboard_summary", {})
    summary["last_update"] = datetime.now().isoformat()
    return summary

@app.get("/api/data-sources")
@app.get("/api/data-collection/status")
def get_data_sources():
    db = load_db()
    return db.get("data_sources", [])

@app.get("/api/alerts")
def get_alerts():
    db = load_db()
    return db.get("alerts", [])

@app.get("/api/network/data")
def get_network_data():
    db = load_db()
    return db.get("network_data", {"nodes": [], "links": []})

@app.get("/api/search")
def search_entities(q: str = ""):
    db = load_db()
    results = db.get("search_entities", [])
    if q:
        results = [r for r in results if q.lower() in r["identifier"].lower()]
    return {"results": results}

@app.get("/api/alerts/suspicious")
def get_suspicious_activity():
    db = load_db()
    return db.get("suspicious_activity", [])

@app.get("/api/reports")
def get_reports():
    db = load_db()
    return db.get("reports", [])

@app.get("/api/network/synthetic")
def get_synthetic_network_data():
    from graph_adapter import build_network_data
    return build_network_data()

@app.get("/api/network/real")
def get_real_network_data(refresh: bool = False):
    """
    Real Elliptic++ (illicit-focused wallet cluster) + real Dread forum
    correlation (PGP alias clusters, reply graph, market activity, and
    wallet-mention bridges) — see backend/real_data/. Cached to disk for
    up to 6h since building it re-scans the full parquet/CSV set;
    pass ?refresh=true to force a rebuild after dropping in new files.
    """
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
def get_geo_activity(refresh: bool = False):
    """Real city-mention/board-activity counts from the Dread archive,
    bucketed into the map's regions. See real_data/geo_signals.py for
    why this is an activity-volume proxy, not real geolocation."""
    from real_data.geo_signals import get_cached_or_build_geo
    try:
        return get_cached_or_build_geo(force=refresh)
    except FileNotFoundError as e:
        return {"counts": {}, "share": {}, "india_board_posts": 0, "error": f"Real data not found: {e}"}