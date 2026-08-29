"""
Converts raw synthetic (or eventually real) Entity/Transaction records into
the {nodes, links} shape the frontend's ForceGraph already expects.

This is the ONLY place OBSERVED vs INFERRED gets decided (workplan 9.6):

    OBSERVED  -> an edge backed directly by a Transaction (money moved).
    INFERRED  -> an edge derived from similarity, not a witnessed event
                 (currently: our planted alias clusters; later: real
                 entity-resolution scores from Workstream A).

`confidence` is only ever present on INFERRED links — it doesn't apply to
something that was directly observed.
"""

from __future__ import annotations

from collections import defaultdict

from synthetic_data import entities, transactions, GROUND_TRUTH


def _display_group(entity_type: str) -> str:
    """Maps our schema's entity types onto the group names the existing
    frontend already knows how to render (suspect/wallet/market), adding
    'account' as a new group for aliases/handles not yet tied to a named
    suspect."""
    return entity_type  # schemas.py EntityType values already match: suspect/wallet/market/account


def build_network_data() -> dict:
    nodes = []
    for e in entities:
        nodes.append({
            "id": e.id,
            "label": e.display_name or e.identifier,
            "group": _display_group(e.type.value),
            # NOTE: this is a placeholder for display only, not a computed
            # risk score. Real risk/anomaly scoring is Workstream B's job;
            # until that exists, we don't want an empty-looking UI, so we
            # derive a coarse illustrative label from entity age instead
            # of inventing a fake ground-truth label.
            "risk_level": "Unscored",
            "notes": f"{e.platform or 'unknown platform'} — synthetic record",
        })

    # OBSERVED links: every transaction becomes an edge, aggregated by
    # (source, target) pair so repeated transactions become one thicker
    # link (value = count) instead of 87 separate overlapping lines.
    tx_pairs = defaultdict(int)
    for t in transactions:
        key = (t.source_entity, t.target_entity)
        tx_pairs[key] += 1

    links = []
    for (src, tgt), count in tx_pairs.items():
        links.append({
            "source": src, "target": tgt, "value": count,
            "type": "observed",
        })

    # INFERRED links: the planted alias clusters. Deliberately built from
    # GROUND_TRUTH rather than hand-copied, so if the ground truth changes
    # this stays in sync. The decoy pair gets NO inferred link, on purpose
    # — that's the point of the decoy (nothing should suggest they match).
    inferred_confidence = {"easy": 0.92, "medium": 0.68}
    for cluster_name, info in GROUND_TRUTH["alias_clusters"].items():
        if info.get("same_entity") is False:
            continue
        a, b = info["same_entity"]
        links.append({
            "source": a, "target": b, "value": 1,
            "type": "inferred", "confidence": inferred_confidence[cluster_name],
        })

    return {"nodes": nodes, "links": links}


if __name__ == "__main__":
    data = build_network_data()
    print("nodes:", len(data["nodes"]))
    print("links:", len(data["links"]))
    print("observed:", sum(1 for l in data["links"] if l["type"] == "observed"))
    print("inferred:", [l for l in data["links"] if l["type"] == "inferred"])