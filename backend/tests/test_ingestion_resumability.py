"""
Permanent Test Infrastructure: Ingestion Resumability & Crash Recovery Test.

Verifies that if ingestion is interrupted mid-file, restarting the pipeline:
1. Resumes from the first pending record using per-record manifest tracking.
2. Produces ZERO duplicate records in canonical tables.
3. Suffers ZERO data loss (all input records successfully ingested).
"""

import os
import sys
import json
from datetime import datetime, timezone

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import engine, SessionLocal, init_db
from data.canonical_schema import (
    EntityModel, IngestionFileManifestModel, IngestionRecordManifestModel
)
from pipelines.ingest_ai_router import IngestionEngine, compute_file_hash


TEST_DATASET_PATH = os.path.join(BACKEND_DIR, "tests", "temp_resumability_dataset.json")


def setup_test_file():
    """Generates dummy dataset."""
    dummy_records = [
        {"id": f"resumable_entity_{i}", "type": "wallet", "address": f"1TestWalletAddress{i:04d}", "risk_score": 50 + i}
        for i in range(50)
    ]
    with open(TEST_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(dummy_records, f, indent=2)


def teardown_test_file():
    """Cleans up test dataset file."""
    if os.path.exists(TEST_DATASET_PATH):
        os.remove(TEST_DATASET_PATH)


def test_ingestion_resumability_after_crash():
    setup_test_file()
    init_db()
    db = SessionLocal()
    engine_instance = IngestionEngine()

    try:
        # 1. Clean up existing test manifest & entity records if present
        db.query(IngestionRecordManifestModel).filter(
            IngestionRecordManifestModel.file_path == TEST_DATASET_PATH
        ).delete()
        db.query(IngestionFileManifestModel).filter(
            IngestionFileManifestModel.file_path == TEST_DATASET_PATH
        ).delete()
        db.query(EntityModel).filter(EntityModel.id.like("resumable_entity_%")).delete()
        db.commit()

        # 2. Simulate Partial Execution: Ingest only first batch (20 records) then simulate crash
        file_hash = compute_file_hash(TEST_DATASET_PATH)
        manifest = IngestionFileManifestModel(
            file_path=TEST_DATASET_PATH, content_hash=file_hash, status="in_progress", total_records=50, processed_records=20
        )
        db.add(manifest)

        with open(TEST_DATASET_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        # Process first 20 records into database and mark manifest mapped
        first_batch = records[:20]
        engine_instance._process_record_batch(db, TEST_DATASET_PATH, first_batch, 0)
        db.commit()

        # Check DB state mid-crash
        count_mid = db.query(EntityModel).filter(EntityModel.id.like("resumable_entity_%")).count()
        assert count_mid == 20, f"Expected 20 records persisted mid-crash, found {count_mid}"

        # 3. Simulate Server Restart: Re-run process_file on the same file
        engine_instance.process_file(TEST_DATASET_PATH)

        # 4. Verify Post-Recovery State
        count_final = db.query(EntityModel).filter(EntityModel.id.like("resumable_entity_%")).count()
        assert count_final == 50, f"Expected exactly 50 records post-recovery, found {count_final} (Duplicates or Lost Records detected!)"

        # Check file manifest completed
        final_manifest = db.query(IngestionFileManifestModel).filter(
            IngestionFileManifestModel.file_path == TEST_DATASET_PATH
        ).first()
        assert final_manifest is not None
        assert final_manifest.status == "completed"
        assert final_manifest.processed_records == 50

        print("\n[SUCCESS] Resumability Crash Recovery Test Passed! 0 Duplicates, 0 Data Loss.")

    finally:
        # Cleanup test records
        db.query(IngestionRecordManifestModel).filter(
            IngestionRecordManifestModel.file_path == TEST_DATASET_PATH
        ).delete()
        db.query(IngestionFileManifestModel).filter(
            IngestionFileManifestModel.file_path == TEST_DATASET_PATH
        ).delete()
        db.query(EntityModel).filter(EntityModel.id.like("resumable_entity_%")).delete()
        db.commit()
        db.close()
        teardown_test_file()


if __name__ == "__main__":
    test_ingestion_resumability_after_crash()
