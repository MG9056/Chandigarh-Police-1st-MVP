"""
Demo Seeder: Synthetic Alerts & Suspicious Activity for Hackathon Judges.

Inserts a small set of clearly synthetic SuspiciousActivity and Alert records
into the existing database so the Alerts & Suspicious Activity Center is
populated for demonstration purposes.

SAFE TO RUN REPEATEDLY -- fully idempotent.
  - Uses stable, deterministic demo UUIDs derived from a fixed namespace.
  - Checks for existing records before inserting; skips any that already exist.
  - Never deletes, truncates, or modifies existing real data.
  - Never calls init_db(), process_raw_records(), or any crawler function.
  - Never touches the production RawRecord pipeline.

Usage (from backend/ directory):
    python pipelines/seed_demo_alerts.py

Decision: raw_record_id is nullable on both SuspiciousActivity and Alert
(confirmed from models.py).  The UI displays case_id and raw_record_id as
optional copyable identifiers, so omitting raw_record_id is correct here --
no fabricated RawRecord rows are needed or created.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Ensure backend root is on sys.path regardless of where the script is invoked from.
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal
from models import SuspiciousActivity, Alert


# ---------------------------------------------------------------------------
# Stable demo namespace -- guarantees deterministic UUIDs across runs.
# The prefix "DEMO:" in dedup_key ensures no collision with real crawler alerts
# (real keys use the format "<raw_record_uuid>:<activity_type>").
# ---------------------------------------------------------------------------

_DEMO_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _demo_uuid(name: str) -> uuid.UUID:
    """Derive a deterministic UUID from the demo namespace and a fixed name."""
    return uuid.uuid5(_DEMO_NS, name)


# ---------------------------------------------------------------------------
# Severity helper -- mirrors alert_generation.py exactly.
# SEVERITY_RED_THRESHOLD    = 0.85   -> "red"
# SEVERITY_YELLOW_THRESHOLD = 0.60   -> "yellow"
# else                               -> "green"
# ---------------------------------------------------------------------------

def _derive_severity(confidence: float) -> str:
    if confidence >= 0.85:
        return "red"
    elif confidence >= 0.60:
        return "yellow"
    else:
        return "green"


# ---------------------------------------------------------------------------
# Alert message helper -- mirrors alert_generation._build_alert_message() exactly.
# ---------------------------------------------------------------------------

_TYPE_LABELS = {
    "high_relevance": "High-Relevance Detection",
    "keyword_burst": "Keyword Burst Detection",
    "entity_indicator": "Entity Indicator Detection",
    "combined_signal": "Combined Signal Detection",
}


def _build_alert_message(activity_type: str, description: str) -> str:
    label = _TYPE_LABELS.get(activity_type, activity_type)
    return f"[{label}] {description}"


# ---------------------------------------------------------------------------
# Demo record definitions.
# Each entry fully specifies one SuspiciousActivity + its corresponding Alert.
# Fields match the exact SuspiciousActivity and Alert model schemas from models.py.
#
# evidence_summary follows the exact structure produced by
# services/suspicious_activity.py:
#   { "score": float, "reasons": [str, ...], "signals": [{"rule": str, "confidence": float, "reasons": [str, ...]}, ...] }
#
# case_id values follow the project existing convention (investigation_id strings).
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)

DEMO_RECORDS = [
    # -- Record 1: high_relevance (RED -- confidence 0.93) --------------------
    {
        "sa_name":       "demo-sa-001-high-relevance-darknet-fentanyl",
        "alert_name":    "demo-alert-001-high-relevance-darknet-fentanyl",
        "case_id":       "DK-2026-001",
        "activity_type": "high_relevance",
        "confidence":    0.93,
        "description": (
            "High-confidence relevant content detected (confidence: 0.93). "
            "Content classified as relevant to illicit activity monitoring. "
            "Darknet forum listing for synthetic opioid bulk supply with stealth domestic shipping "
            "identified in crawler intelligence from onion marketplace source."
        ),
        "evidence_summary": {
            "score": 0.93,
            "reasons": [
                "relevance_label=relevant",
                "relevance_confidence=0.93",
                "reasoning=LLM classified content as high-confidence illicit drug supply listing "
                "with explicit pricing, quantity tiers, and cryptocurrency payment instructions.",
            ],
            "signals": [
                {
                    "rule": "high_relevance",
                    "confidence": 0.93,
                    "reasons": [
                        "relevance_label=relevant",
                        "relevance_confidence=0.93",
                        "reasoning=LLM classified content as high-confidence illicit drug supply listing "
                        "with explicit pricing, quantity tiers, and cryptocurrency payment instructions.",
                    ],
                }
            ],
        },
        "status": "open",
        "detected_at": _NOW - timedelta(hours=2),
    },

    # -- Record 2: keyword_burst (RED -- confidence 0.91) ---------------------
    {
        "sa_name":       "demo-sa-002-keyword-burst-telegram-opioids",
        "alert_name":    "demo-alert-002-keyword-burst-telegram-opioids",
        "case_id":       "DK-2026-001",
        "activity_type": "keyword_burst",
        "confidence":    0.91,
        "description": (
            "Significant suspicious keyword cluster detected (11 matched keywords). "
            "Telegram channel message burst with repeated co-occurrence of monitored terms "
            "associated with pharmaceutical diversion and darknet supply-chain coordination."
        ),
        "evidence_summary": {
            "score": 0.91,
            "reasons": [
                "matched_keyword_count=11",
                "matched_keywords=['fentanyl', 'tramadol', 'darknet', 'btc', 'escrow', "
                "'stealth', 'bulk', 'delivery', 'no-rx', 'prescription', 'drop-point']",
            ],
            "signals": [
                {
                    "rule": "keyword_burst",
                    "confidence": 0.91,
                    "reasons": [
                        "matched_keyword_count=11",
                        "matched_keywords=['fentanyl', 'tramadol', 'darknet', 'btc', 'escrow', "
                        "'stealth', 'bulk', 'delivery', 'no-rx', 'prescription', 'drop-point']",
                    ],
                }
            ],
        },
        "status": "open",
        "detected_at": _NOW - timedelta(hours=7),
    },

    # -- Record 3: combined_signal (RED -- confidence 0.89) -------------------
    {
        "sa_name":       "demo-sa-003-combined-signal-crypto-trafficking",
        "alert_name":    "demo-alert-003-combined-signal-crypto-trafficking",
        "case_id":       "DK-2026-002",
        "activity_type": "combined_signal",
        "confidence":    0.89,
        "description": (
            "Multiple independent risk signals detected (relevance, keywords, entities). "
            "Composite detection score: 0.89. High-relevance content reinforced by keyword "
            "density and high-risk entity extraction -- Bitcoin wallet address co-occurring "
            "with drug trafficking terminology in darknet forum post."
        ),
        "evidence_summary": {
            "score": 0.89,
            "reasons": [
                "relevance_label=relevant",
                "relevance_confidence=0.91",
                "matched_keyword_count=8",
                "matched_keywords=['heroin', 'darknet', 'crypto', 'escrow', 'drop', 'quantity', 'stealth', 'btc']",
                "high_confidence_entities=['BITCOIN_ADDRESS']",
            ],
            "signals": [
                {
                    "rule": "high_relevance",
                    "confidence": 0.91,
                    "reasons": [
                        "relevance_label=relevant",
                        "relevance_confidence=0.91",
                        "reasoning=LLM confirmed darknet supply listing with transaction routing instructions.",
                    ],
                },
                {
                    "rule": "keyword_burst",
                    "confidence": 0.84,
                    "reasons": [
                        "matched_keyword_count=8",
                        "matched_keywords=['heroin', 'darknet', 'crypto', 'escrow', 'drop', 'quantity', 'stealth', 'btc']",
                    ],
                },
                {
                    "rule": "entity_indicator",
                    "confidence": 0.92,
                    "reasons": [
                        "high_confidence_entities=['BITCOIN_ADDRESS']",
                    ],
                },
            ],
        },
        "status": "open",
        "detected_at": _NOW - timedelta(hours=14),
    },

    # -- Record 4: entity_indicator (YELLOW -- confidence 0.78) ---------------
    {
        "sa_name":       "demo-sa-004-entity-indicator-phone-narcotics",
        "alert_name":    "demo-alert-004-entity-indicator-phone-narcotics",
        "case_id":       "DK-2026-003",
        "activity_type": "entity_indicator",
        "confidence":    0.78,
        "description": (
            "High-confidence identifier detected in transaction context. "
            "Phone number extracted with confidence 0.95 co-occurring with narcotics "
            "supply terminology in open-web forum post indexed by crawler."
        ),
        "evidence_summary": {
            "score": 0.78,
            "reasons": [
                "high_confidence_entities=['PHONE_NUMBER']",
                "entity_confidence=0.95",
                "transaction_context=True",
            ],
            "signals": [
                {
                    "rule": "entity_indicator",
                    "confidence": 0.78,
                    "reasons": [
                        "high_confidence_entities=['PHONE_NUMBER']",
                        "entity_confidence=0.95",
                        "transaction_context=True",
                    ],
                }
            ],
        },
        "status": "open",
        "detected_at": _NOW - timedelta(hours=22),
    },

    # -- Record 5: combined_signal (YELLOW -- confidence 0.72) ----------------
    {
        "sa_name":       "demo-sa-005-combined-signal-cannabis-market",
        "alert_name":    "demo-alert-005-combined-signal-cannabis-market",
        "case_id":       "DK-2026-002",
        "activity_type": "combined_signal",
        "confidence":    0.72,
        "description": (
            "Multiple independent risk signals detected (relevance, keywords). "
            "Composite detection score: 0.72. Crawler intelligence record from open "
            "forum thread referencing commercial cannabis supply routes with keyword "
            "density above threshold, moderate LLM relevance confidence."
        ),
        "evidence_summary": {
            "score": 0.72,
            "reasons": [
                "relevance_label=relevant",
                "relevance_confidence=0.74",
                "matched_keyword_count=5",
                "matched_keywords=['cannabis', 'bulk', 'delivery', 'stealth', 'wholesale']",
            ],
            "signals": [
                {
                    "rule": "high_relevance",
                    "confidence": 0.74,
                    "reasons": [
                        "relevance_label=relevant",
                        "relevance_confidence=0.74",
                        "reasoning=LLM classified as likely relevant -- moderate confidence due to ambiguous legal context.",
                    ],
                },
                {
                    "rule": "keyword_burst",
                    "confidence": 0.70,
                    "reasons": [
                        "matched_keyword_count=5",
                        "matched_keywords=['cannabis', 'bulk', 'delivery', 'stealth', 'wholesale']",
                    ],
                },
            ],
        },
        "status": "open",
        "detected_at": _NOW - timedelta(days=1, hours=3),
    },

    # -- Record 6: keyword_burst (YELLOW -- confidence 0.66) ------------------
    {
        "sa_name":       "demo-sa-006-keyword-burst-stimulants-forum",
        "alert_name":    "demo-alert-006-keyword-burst-stimulants-forum",
        "case_id":       "DK-2026-003",
        "activity_type": "keyword_burst",
        "confidence":    0.66,
        "description": (
            "Significant suspicious keyword cluster detected (4 matched keywords). "
            "Darknet-adjacent public forum post containing stimulant procurement "
            "terminology at density above the keyword-burst detection threshold."
        ),
        "evidence_summary": {
            "score": 0.66,
            "reasons": [
                "matched_keyword_count=4",
                "matched_keywords=['mdma', 'stimulants', 'escrow', 'crypto']",
            ],
            "signals": [
                {
                    "rule": "keyword_burst",
                    "confidence": 0.66,
                    "reasons": [
                        "matched_keyword_count=4",
                        "matched_keywords=['mdma', 'stimulants', 'escrow', 'crypto']",
                    ],
                }
            ],
        },
        "status": "acknowledged",
        "detected_at": _NOW - timedelta(days=2, hours=5),
    },

    # -- Record 7: entity_indicator (GREEN -- confidence 0.54) ----------------
    {
        "sa_name":       "demo-sa-007-entity-indicator-eth-address-low",
        "alert_name":    "demo-alert-007-entity-indicator-eth-address-low",
        "case_id":       "DK-2026-004",
        "activity_type": "entity_indicator",
        "confidence":    0.54,
        "description": (
            "High-confidence identifier detected in transaction context. "
            "Ethereum wallet address extracted with confidence 0.91 from forum post "
            "referencing transaction routing; overall risk signal remains informational "
            "due to ambiguous surrounding context."
        ),
        "evidence_summary": {
            "score": 0.54,
            "reasons": [
                "high_confidence_entities=['ETHEREUM_ADDRESS']",
                "entity_confidence=0.91",
                "transaction_context=True",
            ],
            "signals": [
                {
                    "rule": "entity_indicator",
                    "confidence": 0.54,
                    "reasons": [
                        "high_confidence_entities=['ETHEREUM_ADDRESS']",
                        "entity_confidence=0.91",
                        "transaction_context=True",
                    ],
                }
            ],
        },
        "status": "resolved",
        "detected_at": _NOW - timedelta(days=3, hours=11),
    },

    # -- Record 8: high_relevance (GREEN -- confidence 0.45) ------------------
    {
        "sa_name":       "demo-sa-008-high-relevance-low-conf-opiate",
        "alert_name":    "demo-alert-008-high-relevance-low-conf-opiate",
        "case_id":       "DK-2026-004",
        "activity_type": "high_relevance",
        "confidence":    0.45,
        "description": (
            "High-confidence relevant content detected (confidence: 0.45). "
            "Content classified as relevant to illicit activity monitoring. "
            "Forum thread discussing opiate withdrawal management -- LLM flagged "
            "potential supply-side references with low confidence; placed in "
            "review queue due to ambiguous medical/illicit context."
        ),
        "evidence_summary": {
            "score": 0.45,
            "reasons": [
                "relevance_label=relevant",
                "relevance_confidence=0.45",
                "reasoning=LLM flagged marginal relevance -- content contains opiate terminology "
                "but context is primarily harm-reduction discussion. Low confidence.",
            ],
            "signals": [
                {
                    "rule": "high_relevance",
                    "confidence": 0.45,
                    "reasons": [
                        "relevance_label=relevant",
                        "relevance_confidence=0.45",
                        "reasoning=LLM flagged marginal relevance -- content contains opiate terminology "
                        "but context is primarily harm-reduction discussion. Low confidence.",
                    ],
                }
            ],
        },
        "status": "dismissed",
        "detected_at": _NOW - timedelta(days=4, hours=9),
    },
]


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

def seed_demo_alerts() -> None:
    print("=" * 70)
    print("DEMO SEEDER: Synthetic Alerts & Suspicious Activity")
    print("Project Dark Knight -- Hackathon Judge Demonstration Data")
    print("=" * 70)

    db = SessionLocal()
    try:
        inserted_sa = 0
        skipped_sa = 0
        inserted_alerts = 0
        skipped_alerts = 0

        for rec in DEMO_RECORDS:
            sa_id    = _demo_uuid(rec["sa_name"])
            alert_id = _demo_uuid(rec["alert_name"])

            # Idempotency: skip if SuspiciousActivity already exists.
            existing_sa = db.query(SuspiciousActivity).filter(
                SuspiciousActivity.id == sa_id
            ).first()

            if existing_sa:
                print(f"  [SKIP] SuspiciousActivity already exists: {sa_id} ({rec['activity_type']})")
                skipped_sa += 1
            else:
                sa = SuspiciousActivity(
                    id=sa_id,
                    raw_record_id=None,   # nullable -- no fabricated RawRecord needed
                    case_id=rec["case_id"],
                    activity_type=rec["activity_type"],
                    description=rec["description"],
                    confidence=rec["confidence"],
                    evidence_summary=rec["evidence_summary"],
                    status=rec["status"],
                    detected_at=rec["detected_at"],
                    created_at=rec["detected_at"],
                )
                db.add(sa)
                db.flush()  # obtain id before creating alert FK
                inserted_sa += 1
                print(f"  [INSERT] SuspiciousActivity: {sa_id} | {rec['activity_type']} | confidence={rec['confidence']}")

            # Idempotency: skip if Alert already exists.
            existing_alert = db.query(Alert).filter(
                Alert.id == alert_id
            ).first()

            if existing_alert:
                print(f"  [SKIP] Alert already exists:              {alert_id}")
                skipped_alerts += 1
            else:
                severity  = _derive_severity(rec["confidence"])
                message   = _build_alert_message(rec["activity_type"], rec["description"])
                # dedup_key uses DEMO: prefix so it can never collide with real crawler keys.
                # Real keys use the format "<raw_record_uuid>:<activity_type>".
                dedup_key = f"DEMO:{rec['sa_name']}"

                # Alert.status: mirror SA status using Alert status vocabulary.
                # SA statuses: open, acknowledged, resolved, dismissed
                # Alert statuses: active, acknowledged, resolved
                # "open" SA -> "active" Alert; "dismissed" SA -> "resolved" Alert
                if rec["status"] == "open":
                    alert_status = "active"
                elif rec["status"] == "dismissed":
                    alert_status = "resolved"
                else:
                    alert_status = rec["status"]  # acknowledged, resolved pass through

                alert = Alert(
                    id=alert_id,
                    suspicious_activity_id=sa_id,
                    raw_record_id=None,   # nullable -- matches SA above
                    case_id=rec["case_id"],
                    severity=severity,
                    message=message,
                    status=alert_status,
                    dedup_key=dedup_key,
                    created_at=rec["detected_at"],
                )
                db.add(alert)
                inserted_alerts += 1
                print(f"  [INSERT] Alert:              {alert_id} | severity={severity} | dedup_key={dedup_key}")

        db.commit()

        print()
        print("=" * 70)
        print("DEMO SEED COMPLETE.")
        print(f"  SuspiciousActivity -> inserted: {inserted_sa}, skipped (already existed): {skipped_sa}")
        print(f"  Alerts             -> inserted: {inserted_alerts}, skipped (already existed): {skipped_alerts}")
        print("=" * 70)

    except Exception as exc:
        db.rollback()
        print("\n[ERROR] Demo seed failed -- rolling back. No partial data written.")
        print(f"  Exception: {exc}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_alerts()
