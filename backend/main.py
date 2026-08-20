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
