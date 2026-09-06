"""
Entity and geography aggregation over RawRecord data.

These functions aggregate extracted entity candidates and geographic signals
from the crawler pipeline's RawRecord table — WITHOUT any new tables or schema.
They are called by both investigation-scoped and global API endpoints.

Design notes:
- aggregate_entities: builds a co-occurrence node/edge graph from
  RawRecord.extracted_candidates and .structured_intelligence.entities.
  Edges are labelled CO_OCCURRENCE (observational — two entities appeared in
  the same record; not a confirmed relationship).
- aggregate_geography: resolves LOCATION candidates against the India gazetteer
  (PLACES + ALIASES) and tallies mention counts per city.
- case_id=None → global, unscoped view across all investigations.
- case_id=<str> → scoped to records where RawRecord.case_id == that value.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from crawler.models.raw_record import RawRecord


def aggregate_entities(
    db: Session,
    case_id: Optional[str] = None,
    limit_records: int = 500,
) -> dict:
    """
    Aggregate extracted entity candidates into a force-graph node/edge structure.

    Node deduplication key: (type, value) — same entity mentioned multiple times
    increments `mentions` on the same node.

    Edge semantics: CO_OCCURRENCE — two entities appeared in the same source record.
    This is purely observational and does NOT imply a confirmed relationship between
    them. The edge `weight` counts how many records they co-appeared in.

    Args:
        db: SQLAlchemy session.
        case_id: If set, restrict to RawRecord.case_id == case_id. If None, global.
        limit_records: Max records to process (prevents runaway queries on large DBs).

    Returns:
        {
            "nodes": [{"id": "<type>:<value>", "type": str, "value": str, "mentions": int}],
            "links": [{"source": str, "target": str, "weight": int, "relationship": "CO_OCCURRENCE"}],
            "record_count": int,
            "scope": "investigation" | "global",
        }
    """
    query = db.query(RawRecord)
    if case_id:
        query = query.filter(RawRecord.case_id == case_id)
    records = query.order_by(RawRecord.fetched_at.desc()).limit(limit_records).all()

    nodes: dict[tuple, dict] = {}   # (type, value) → node dict
    edges: dict[frozenset, dict] = {}  # frozenset({key_a, key_b}) → edge dict

    for rec in records:
        entity_keys_this_record: list[tuple] = []

        # --- Primary source: extracted_candidates (spaCy / GLiNER output) ---
        for cand in (rec.extracted_candidates or []):
            etype = cand.get("type") or cand.get("entity_type")
            evalue = cand.get("value") or cand.get("text")
            if not etype or not evalue:
                continue
            key = (str(etype).upper(), str(evalue).strip())
            if key not in nodes:
                nodes[key] = {
                    "id": f"{key[0]}:{key[1]}",
                    "type": key[0],
                    "value": key[1],
                    "mentions": 0,
                }
            nodes[key]["mentions"] += 1
            entity_keys_this_record.append(key)

        # --- Secondary source: structured_intelligence.entities (LLM output) ---
        si = rec.structured_intelligence or {}
        for si_entity in si.get("entities", []):
            etype = si_entity.get("type") or si_entity.get("entity_type")
            evalue = si_entity.get("value") or si_entity.get("text")
            if not etype or not evalue:
                continue
            key = (str(etype).upper(), str(evalue).strip())
            if key not in nodes:
                nodes[key] = {
                    "id": f"{key[0]}:{key[1]}",
                    "type": key[0],
                    "value": key[1],
                    "mentions": 0,
                }
            nodes[key]["mentions"] += 1
            entity_keys_this_record.append(key)

        # --- Co-occurrence edges (observational) ---
        # Deduplicate keys within this record so we don't double-count self-loops
        seen_in_record = list(dict.fromkeys(entity_keys_this_record))
        for i in range(len(seen_in_record)):
            for j in range(i + 1, len(seen_in_record)):
                k_a, k_b = seen_in_record[i], seen_in_record[j]
                edge_key = frozenset([k_a, k_b])
                if edge_key not in edges:
                    edges[edge_key] = {
                        "source": nodes[k_a]["id"],
                        "target": nodes[k_b]["id"],
                        "weight": 0,
                        # CO_OCCURRENCE = observational only; not a confirmed relationship
                        "relationship": "CO_OCCURRENCE",
                    }
                edges[edge_key]["weight"] += 1

    return {
        "nodes": list(nodes.values()),
        "links": list(edges.values()),
        "record_count": len(records),
        "scope": "investigation" if case_id else "global",
    }


def aggregate_geography(
    db: Session,
    case_id: Optional[str] = None,
    limit_records: int = 500,
) -> dict:
    """
    Extract LOCATION-type entity candidates and resolve against the India gazetteer.

    Reuses real_data.india_gazetteer.PLACES (canonical_name → (lat, lon)) and
    ALIASES (lowercase_alias → canonical_name). Does NOT call any external geocoding
    service; purely in-memory lookup against the ~120-city static gazetteer.

    Resolution rules (in order):
    1. Exact match in PLACES (case-insensitive).
    2. Alias match in ALIASES (lowercase comparison).
    If neither matches, the location candidate is discarded.

    Args:
        db: SQLAlchemy session.
        case_id: If set, restrict to RawRecord.case_id == case_id. If None, global.
        limit_records: Max records to process.

    Returns:
        {
            "places": [{"name": str, "lat": float, "lon": float, "count": int}],
            "scope": "investigation" | "global",
            "record_count": int,
        }
    """
    # Import gazetteer — adapt to what actually exists (no resolve_place_name function)
    from real_data.india_gazetteer import PLACES, ALIASES

    # Build a lookup: lowercase canonical name → canonical name (for case-insensitive match)
    places_lower: dict[str, str] = {name.lower(): name for name in PLACES}

    query = db.query(RawRecord)
    if case_id:
        query = query.filter(RawRecord.case_id == case_id)
    records = query.order_by(RawRecord.fetched_at.desc()).limit(limit_records).all()

    place_counts: dict[str, dict] = {}  # canonical_name → {name, lat, lon, count}

    for rec in records:
        for cand in (rec.extracted_candidates or []):
            etype = cand.get("type") or cand.get("entity_type")
            if str(etype).upper() not in ("LOCATION", "GPE", "LOC"):
                continue
            raw_value = (cand.get("value") or cand.get("text") or "").strip()
            if not raw_value:
                continue

            canonical = _resolve_place(raw_value, places_lower, ALIASES)
            if not canonical:
                continue

            lat, lon = PLACES[canonical]
            if canonical not in place_counts:
                place_counts[canonical] = {
                    "name": canonical,
                    "lat": lat,
                    "lon": lon,
                    "count": 0,
                }
            place_counts[canonical]["count"] += 1

    return {
        "places": sorted(place_counts.values(), key=lambda p: -p["count"]),
        "scope": "investigation" if case_id else "global",
        "record_count": len(records),
    }


def _resolve_place(
    raw: str,
    places_lower: dict[str, str],
    aliases: dict[str, str],
) -> Optional[str]:
    """
    Resolve a raw place-name string to a canonical gazetteer name.

    Returns the canonical name (key in PLACES) or None if unresolvable.
    """
    raw_lower = raw.lower().strip()

    # 1. Direct case-insensitive match in PLACES
    if raw_lower in places_lower:
        return places_lower[raw_lower]

    # 2. Alias lookup
    if raw_lower in aliases:
        canonical = aliases[raw_lower]
        return canonical  # aliases always resolve to valid PLACES keys

    return None
