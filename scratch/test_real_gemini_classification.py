import sys
import os
import sqlite3
import json
import logging
from io import StringIO

backend_dir = r"c:\Users\shrih\Desktop\lmaoded\Chandigarh-Police-1st-MVP\backend"
sys.path.insert(0, backend_dir)

from database import engine, SessionLocal, init_db
from data.canonical_schema import EntityModel, IngestionFileManifestModel, IngestionRecordManifestModel
from pipelines.ingest_ai_router import IngestionEngine, HybridClassifier
import data.canonical_schema_extensions as extensions

# Capture log output to string and stdout
log_capture_string = StringIO()
ch = logging.StreamHandler(log_capture_string)
ch.setLevel(logging.INFO)

sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.INFO)

logger = logging.getLogger("ingest_ai_router")
logger.addHandler(ch)
logger.addHandler(sh)

test_csv = os.path.join(backend_dir, "test_data_drone_telemetry.csv")
with open(test_csv, "w", encoding="utf-8") as f:
    f.write("drone_id,pilot_callsign,signal_frequency_ghz,altitude_meters,surveillance_zone\n")
    f.write("DRONE-SURV-101,ViperSky,5.8GHz,220.5,Sector 17 North\n")
    f.write("DRONE-SURV-102,FalconEye,2.4GHz,185.0,Model Town South\n")

print(f"Created novel synthetic dataset file: '{test_csv}'\n")

# Verify Classifier Mode
classifier = HybridClassifier()
print(f"Active Mode Detected: {classifier.active_mode}\n")

# Run Ingestion Engine
engine_instance = IngestionEngine()
engine_instance.process_file(test_csv)

# Query database for ingested novel entities
db = SessionLocal()
ingested_entities = db.query(EntityModel).filter(EntityModel.metadata_json.like("%gemini_ai%")).all()

print("\n=== INGESTED CANONICAL ENTITIES CLASSIFIED BY GEMINI AI ===")
for e in ingested_entities:
    print(f"ID: {e.id} | Type: {e.type} | Identifier: {e.identifier} | Display Name: {e.display_name} | Metadata: {e.metadata_json}")

# Check new_categories_created.log
new_cat_log = os.path.join(backend_dir, "new_categories_created.log")
if os.path.exists(new_cat_log):
    with open(new_cat_log, "r", encoding="utf-8") as f:
        print("\n=== LITERALLY CAPTURED new_categories_created.log ===")
        print(f.read())

# Clean up test file and test DB records
if os.path.exists(test_csv):
    os.remove(test_csv)

db.query(IngestionRecordManifestModel).filter(IngestionRecordManifestModel.file_path == test_csv).delete()
db.query(IngestionFileManifestModel).filter(IngestionFileManifestModel.file_path == test_csv).delete()
db.query(EntityModel).filter(EntityModel.metadata_json.like("%gemini_ai%")).delete()
db.commit()
db.close()
