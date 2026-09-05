"""
Detection Pipeline Service.

Unified entry point to process RawRecords through the suspicious activity
detection and alert generation pipeline. This is a synchronous callable
that can be invoked by tests, existing crawler orchestration, or a future
scheduled pipeline.

Does NOT build a background scheduler. Does NOT tightly couple to a
specific crawler collector. Does NOT modify RawRecord status.
"""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from crawler.models.raw_record import RawRecord
from models import SuspiciousActivity
from services.suspicious_activity import detect_suspicious_activity
from services.alert_generation import generate_alert
from audit_service import create_audit_log

logger = logging.getLogger(__name__)


def process_raw_records(
    db: Session,
    record_ids: Optional[list[UUID]] = None,
) -> dict:
    """
    Process RawRecords through the detection and alert generation pipeline.

    If record_ids is provided, processes only those specific records.
    Otherwise, processes all RawRecords that haven't been analyzed yet
    (relevance_label is not null, indicating they've been through the
    crawler pipeline).

    Returns a summary dict with counts of processed, detected, and alerted records.
    """
    summary = {
        "records_processed": 0,
        "suspicious_activities_created": 0,
        "alerts_created": 0,
        "skipped_dedup": 0,
        "errors": 0,
    }

    try:
        # Query records to process
        query = db.query(RawRecord)
        if record_ids:
            query = query.filter(RawRecord.id.in_(record_ids))
        else:
            # Process records that have been through the crawler pipeline
            # (have a relevance_label set), regardless of their status.
            # We do NOT modify RawRecord status.
            query = query.filter(RawRecord.relevance_label.isnot(None))

        records = query.all()
        logger.info(f"Detection pipeline: processing {len(records)} RawRecords")

        for record in records:
            try:
                # Snapshot existing SA ids for this record before detection
                # so we can reliably tell if a new one was just created.
                # (db.flush() inside detect_suspicious_activity moves the object
                # out of db.new into the identity map, making `sa in db.new` unreliable.)
                pre_existing_sa_ids = {
                    row.id for row in db.query(SuspiciousActivity).filter(
                        SuspiciousActivity.raw_record_id == record.id
                    ).all()
                }

                # Step 1: Run detection
                sa = detect_suspicious_activity(record, db)

                if sa is None:
                    summary["records_processed"] += 1
                    continue

                # New if ID wasn't in the snapshot taken before detection
                is_new_sa = sa.id not in pre_existing_sa_ids
                if is_new_sa:
                    summary["suspicious_activities_created"] += 1

                    # Step 2: Generate alert from detection
                    alert = generate_alert(sa, db)
                    if alert is not None:
                        summary["alerts_created"] += 1
                    else:
                        summary["skipped_dedup"] += 1
                else:
                    summary["skipped_dedup"] += 1

                summary["records_processed"] += 1

            except Exception as e:
                logger.error(
                    f"Error processing record {record.id}: {e}",
                    exc_info=True,
                )
                summary["errors"] += 1

        # Commit all changes in a single transaction
        db.commit()

        # Audit log the pipeline run (only IDs/counts, no raw content)
        if summary["suspicious_activities_created"] > 0 or summary["alerts_created"] > 0:
            create_audit_log(
                db=db,
                action="DETECTION_PIPELINE_RUN",
                result="SUCCESS",
                resource_type="DetectionPipeline",
                metadata={
                    "records_processed": summary["records_processed"],
                    "suspicious_activities_created": summary["suspicious_activities_created"],
                    "alerts_created": summary["alerts_created"],
                    "skipped_dedup": summary["skipped_dedup"],
                    "errors": summary["errors"],
                },
            )

    except Exception as e:
        db.rollback()
        logger.error(f"Detection pipeline failed: {e}", exc_info=True)
        summary["errors"] += 1

        create_audit_log(
            db=db,
            action="DETECTION_PIPELINE_RUN",
            result="FAILURE",
            resource_type="DetectionPipeline",
            metadata={
                "error": str(e)[:200],  # Truncate to avoid storing excessive data
            },
        )

    logger.info(f"Detection pipeline complete: {summary}")
    return summary
