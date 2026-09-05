"""
Suspicious Activity Detection Service.

Operates on existing RawRecord data and produces SuspiciousActivity detections
using explainable, rule-based signal analysis. Does NOT claim to be a trained
ML model — all scores are deterministic detection/risk confidence scores
derived from the combination of available signals.

Detection Rules:
  A — High Relevance: relevant classification + high confidence
  B — Keyword Burst: significant suspicious keyword matches
  C — Entity Indicators: high-confidence identifiers in transaction context
  D — Combined Signal: weighted composite of independent signals
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

from models import SuspiciousActivity
from crawler.models.raw_record import RawRecord

logger = logging.getLogger(__name__)

# ── Configurable Thresholds ──────────────────────────────────────────────────

# Rule A: minimum relevance confidence to flag as suspicious
HIGH_RELEVANCE_CONFIDENCE_THRESHOLD = 0.80

# Rule B: minimum number of matched suspicious keywords
MIN_SUSPICIOUS_KEYWORD_COUNT = 3

# Rule C: minimum entity extraction confidence for identifier-based flagging
MIN_ENTITY_CONFIDENCE = 0.90

# Entity types considered high-risk identifiers
HIGH_RISK_ENTITY_TYPES = {"BITCOIN_ADDRESS", "ETHEREUM_ADDRESS", "PHONE_NUMBER"}

# Rule D combined signal weights
WEIGHT_RELEVANCE = 0.35
WEIGHT_KEYWORDS = 0.25
WEIGHT_ENTITIES = 0.25
WEIGHT_CONFIDENCE = 0.15

# Minimum combined score to produce a combined_signal detection
MIN_COMBINED_SCORE = 0.65


def _evaluate_rule_a(record: RawRecord) -> Optional[dict]:
    """
    Rule A — High Relevance.
    If relevance_label == 'relevant' and relevance_confidence is sufficiently high,
    produce a suspicious activity candidate.
    """
    relevance_label = record.relevance_label
    relevance_confidence = float(record.relevance_confidence) if record.relevance_confidence is not None else 0.0

    if relevance_label == "relevant" and relevance_confidence >= HIGH_RELEVANCE_CONFIDENCE_THRESHOLD:
        reasons = [
            f"relevance_label={relevance_label}",
            f"relevance_confidence={relevance_confidence:.2f}",
        ]
        if record.relevance_reasoning:
            reasons.append(f"reasoning={record.relevance_reasoning}")

        return {
            "activity_type": "high_relevance",
            "confidence": min(relevance_confidence, 1.0),
            "description": (
                f"High-confidence relevant content detected "
                f"(confidence: {relevance_confidence:.2f}). "
                f"Content classified as relevant to illicit activity monitoring."
            ),
            "reasons": reasons,
        }
    return None


def _evaluate_rule_b(record: RawRecord) -> Optional[dict]:
    """
    Rule B — Keyword Burst / High-Risk Keyword Signal.
    Detect records with a meaningful number of suspicious keyword matches.
    Uses a configurable threshold so behavior is explicit.
    """
    matched_keywords = record.matched_keywords or []
    if not isinstance(matched_keywords, list):
        matched_keywords = []

    keyword_count = len(matched_keywords)
    if keyword_count < MIN_SUSPICIOUS_KEYWORD_COUNT:
        return None

    # Scale confidence based on keyword density (3 keywords = 0.65, 6+ = 0.90)
    base_confidence = min(0.50 + (keyword_count * 0.08), 0.95)

    reasons = [
        f"matched_keyword_count={keyword_count}",
        f"matched_keywords={matched_keywords[:10]}",  # Cap at 10 for readability
    ]

    return {
        "activity_type": "keyword_burst",
        "confidence": round(base_confidence, 2),
        "description": (
            f"Significant keyword burst detected: {keyword_count} suspicious keywords matched "
            f"({', '.join(matched_keywords[:5])}{'...' if keyword_count > 5 else ''})."
        ),
        "reasons": reasons,
    }


def _evaluate_rule_c(record: RawRecord) -> Optional[dict]:
    """
    Rule C — Multiple Transaction/Entity Indicators.
    If a record contains high-confidence wallet/address/phone/entity candidates
    together with relevant marketplace/transaction context, increase the risk signal.
    """
    candidates = record.extracted_candidates or []
    if not isinstance(candidates, list):
        candidates = []

    # Find high-confidence identifiers of high-risk types
    high_risk_entities = [
        c for c in candidates
        if isinstance(c, dict)
        and c.get("type") in HIGH_RISK_ENTITY_TYPES
        and float(c.get("confidence", 0)) >= MIN_ENTITY_CONFIDENCE
    ]

    if not high_risk_entities:
        return None

    # Check for marketplace/transaction context via relevance_label or keywords
    has_context = (
        record.relevance_label == "relevant"
        or len(record.matched_keywords or []) >= 1
    )
    if not has_context:
        return None

    entity_types_found = list(set(e.get("type") for e in high_risk_entities))
    max_entity_confidence = max(float(e.get("confidence", 0)) for e in high_risk_entities)

    # Confidence is boosted by having multiple different entity types
    base_confidence = min(0.70 + (len(entity_types_found) * 0.08), 0.95)

    reasons = [
        f"high_confidence_identifiers_detected={entity_types_found}",
        f"identifier_count={len(high_risk_entities)}",
        f"max_entity_confidence={max_entity_confidence:.2f}",
        f"marketplace_context={'relevant' if record.relevance_label == 'relevant' else 'keyword_match'}",
    ]

    return {
        "activity_type": "entity_indicator",
        "confidence": round(base_confidence, 2),
        "description": (
            f"High-confidence identifiers detected ({', '.join(entity_types_found)}) "
            f"in marketplace/transaction context. "
            f"{len(high_risk_entities)} identifier(s) with confidence >= {MIN_ENTITY_CONFIDENCE}."
        ),
        "reasons": reasons,
    }


def _evaluate_rule_d(record: RawRecord) -> Optional[dict]:
    """
    Rule D — Strong Combined Signal.
    Combines independent signals into an explainable composite risk score.
    Only fires when multiple signals are present simultaneously.
    """
    reasons = []
    signal_scores = {}

    # Signal 1: Relevance classification
    relevance_confidence = float(record.relevance_confidence) if record.relevance_confidence is not None else 0.0
    if record.relevance_label == "relevant":
        signal_scores["relevance"] = min(relevance_confidence, 1.0)
        reasons.append(f"relevance_label={record.relevance_label}")
        reasons.append(f"relevance_confidence={relevance_confidence:.2f}")

    # Signal 2: Keyword matches
    matched_keywords = record.matched_keywords or []
    if isinstance(matched_keywords, list) and len(matched_keywords) > 0:
        keyword_score = min(len(matched_keywords) / 6.0, 1.0)
        signal_scores["keywords"] = keyword_score
        reasons.append(f"matched_keywords={matched_keywords[:5]}")

    # Signal 3: Entity extraction
    candidates = record.extracted_candidates or []
    if isinstance(candidates, list) and len(candidates) > 0:
        high_conf_entities = [
            c for c in candidates
            if isinstance(c, dict) and float(c.get("confidence", 0)) >= 0.80
        ]
        if high_conf_entities:
            entity_score = min(len(high_conf_entities) / 3.0, 1.0)
            signal_scores["entities"] = entity_score
            entity_types = list(set(c.get("type", "unknown") for c in high_conf_entities))
            reasons.append(f"high_confidence_entities={entity_types}")

    # Need at least 2 independent signals for combined detection
    if len(signal_scores) < 2:
        return None

    # Weighted composite score
    weights = {
        "relevance": WEIGHT_RELEVANCE,
        "keywords": WEIGHT_KEYWORDS,
        "entities": WEIGHT_ENTITIES,
    }
    total_weight = sum(weights.get(k, 0) for k in signal_scores)
    if total_weight == 0:
        return None

    # Add base confidence signal weight
    combined_score = sum(
        signal_scores[k] * weights.get(k, WEIGHT_CONFIDENCE)
        for k in signal_scores
    ) / total_weight
    # Boost slightly for having more signals
    combined_score = min(combined_score + (len(signal_scores) - 1) * 0.05, 1.0)

    if combined_score < MIN_COMBINED_SCORE:
        return None

    return {
        "activity_type": "combined_signal",
        "confidence": round(combined_score, 2),
        "description": (
            f"Multiple independent risk signals detected "
            f"({', '.join(signal_scores.keys())}). "
            f"Composite detection score: {combined_score:.2f}."
        ),
        "reasons": reasons,
    }


def detect_suspicious_activity(
    record: RawRecord,
    db: Session,
) -> Optional[SuspiciousActivity]:
    """
    Evaluate all detection rules against a RawRecord and persist the highest-confidence
    detection as a SuspiciousActivity. Deduplicates by raw_record_id + activity_type.

    Returns the created/existing SuspiciousActivity, or None if no detection triggered.
    """
    # Evaluate all rules
    detections = []
    for rule_fn in [_evaluate_rule_a, _evaluate_rule_b, _evaluate_rule_c, _evaluate_rule_d]:
        result = rule_fn(record)
        if result is not None:
            detections.append(result)

    if not detections:
        return None

    # Pick the highest-confidence detection
    best = max(detections, key=lambda d: d["confidence"])

    # Deduplication: check if we already have this detection for this record
    existing = db.query(SuspiciousActivity).filter(
        SuspiciousActivity.raw_record_id == record.id,
        SuspiciousActivity.activity_type == best["activity_type"],
    ).first()

    if existing:
        logger.debug(
            f"SuspiciousActivity already exists for record {record.id} "
            f"with type {best['activity_type']}, skipping."
        )
        return existing

    # Collect ALL reasons from every firing rule for full explainability
    all_reasons = []
    all_signals = []
    for det in detections:
        all_reasons.extend(det["reasons"])
        all_signals.append({
            "rule": det["activity_type"],
            "confidence": det["confidence"],
            "reasons": det["reasons"],
        })

    # Create new SuspiciousActivity
    sa = SuspiciousActivity(
        raw_record_id=record.id,
        case_id=record.case_id,
        activity_type=best["activity_type"],
        description=best["description"],
        confidence=best["confidence"],
        evidence_summary={
            "score": best["confidence"],
            "reasons": all_reasons,
            "signals": all_signals,
        },
        status="open",
    )
    db.add(sa)
    db.flush()  # Assign ID without full commit (caller controls transaction)

    logger.info(
        f"SuspiciousActivity detected: type={best['activity_type']}, "
        f"confidence={best['confidence']}, record={record.id}"
    )

    return sa
