"""
Alert Generation Service.

Converts SuspiciousActivity detections into actionable Alert records.
Severity is deterministically derived from configurable confidence thresholds.
Deduplication prevents duplicate alerts for the same underlying detection.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

from models import Alert, SuspiciousActivity

logger = logging.getLogger(__name__)

# ── Configurable Severity Thresholds ─────────────────────────────────────────
# These map detection confidence score ranges to frontend-compatible severity
# color strings ("red", "yellow", "green").

SEVERITY_RED_THRESHOLD = 0.85      # >= 0.85 → critical (red)
SEVERITY_YELLOW_THRESHOLD = 0.60   # >= 0.60 → warning (yellow)
# < 0.60 → informational (green)


def _derive_severity(confidence: float) -> str:
    """
    Deterministically maps a detection confidence score to a severity string.
    Uses configurable thresholds rather than hardcoding throughout the code.
    """
    if confidence >= SEVERITY_RED_THRESHOLD:
        return "red"
    elif confidence >= SEVERITY_YELLOW_THRESHOLD:
        return "yellow"
    else:
        return "green"


def _build_dedup_key(suspicious_activity: SuspiciousActivity) -> str:
    """
    Builds a deterministic deduplication key from the underlying detection.
    Format: "{raw_record_id}:{activity_type}"

    If the same underlying record is processed repeatedly, the service will
    not create unlimited duplicate alerts.
    """
    raw_id = str(suspicious_activity.raw_record_id) if suspicious_activity.raw_record_id else "no_record"
    return f"{raw_id}:{suspicious_activity.activity_type}"


def _build_alert_message(suspicious_activity: SuspiciousActivity) -> str:
    """
    Builds a human-readable alert message from the suspicious activity
    description and type. Tied to the underlying detection, not invented.
    """
    type_labels = {
        "high_relevance": "High-Relevance Detection",
        "keyword_burst": "Keyword Burst Detection",
        "entity_indicator": "Entity Indicator Detection",
        "combined_signal": "Combined Signal Detection",
    }
    label = type_labels.get(suspicious_activity.activity_type, suspicious_activity.activity_type)
    return f"[{label}] {suspicious_activity.description}"


def generate_alert(
    suspicious_activity: SuspiciousActivity,
    db: Session,
) -> Optional[Alert]:
    """
    Generate an Alert from a SuspiciousActivity detection.

    - Severity is deterministically derived from the detection confidence.
    - Deduplication uses a key composed of raw_record_id + activity_type.
    - If an Alert with the same dedup_key already exists, returns None.

    Returns the created Alert, or None if deduplicated.
    """
    dedup_key = _build_dedup_key(suspicious_activity)

    # Check for existing alert with same dedup_key
    existing = db.query(Alert).filter(Alert.dedup_key == dedup_key).first()
    if existing:
        logger.debug(
            f"Alert already exists with dedup_key={dedup_key}, skipping."
        )
        return None

    confidence = float(suspicious_activity.confidence) if suspicious_activity.confidence is not None else 0.0
    severity = _derive_severity(confidence)
    message = _build_alert_message(suspicious_activity)

    alert = Alert(
        suspicious_activity_id=suspicious_activity.id,
        raw_record_id=suspicious_activity.raw_record_id,
        case_id=suspicious_activity.case_id,
        severity=severity,
        message=message,
        status="active",
        dedup_key=dedup_key,
    )
    db.add(alert)
    db.flush()  # Assign ID without full commit (caller controls transaction)

    logger.info(
        f"Alert generated: severity={severity}, dedup_key={dedup_key}, "
        f"suspicious_activity_id={suspicious_activity.id}"
    )

    return alert
