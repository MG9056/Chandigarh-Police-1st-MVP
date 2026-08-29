"""
Phase 1 — synthetic data generator.

Generates raw Entity / Observation / Transaction / Region records that
conform to `data/schemas.py`, with a small number of DELIBERATE, KNOWN
patterns planted inside otherwise-random noise. The point of planting
known patterns is so we can later check whether our actual intelligence
logic (entity resolution, anomaly detection, graph metrics, hotspot
scoring) correctly finds them — instead of just eyeballing whether output
"looks plausible".

This module is a stand-in for real ingestion. It only ever produces
objects typed against `schemas.py`, so when real data becomes available
later, it can replace this module without changing anything downstream.

GROUND_TRUTH at the bottom documents every pattern planted, in one place,
so it's easy to check detection logic against a known answer key.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from data.schemas import (
    Entity, EntityType, Observation, Transaction,
    Region, DetailedLocation, BoundingBox,
)

random.seed(42)  # deterministic — same dataset every run

NOW = datetime(2026, 8, 20, 12, 0, 0)


def _iso_minus(days=0, hours=0, minutes=0):
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


# ---------------------------------------------------------------------------
# Regions (Piece: geographic hot/cold pattern)
# ---------------------------------------------------------------------------

REGIONS = [
    Region(id="chandigarh", name="Chandigarh", lat=30.7333, lon=76.7794,
           bounding_box=BoundingBox(min_lat=30.65, max_lat=30.80, min_lon=76.70, max_lon=76.85)),
    Region(id="ludhiana", name="Ludhiana", lat=30.9010, lon=75.8573,
           bounding_box=BoundingBox(min_lat=30.82, max_lat=30.98, min_lon=75.78, max_lon=75.94)),
    Region(id="amritsar", name="Amritsar", lat=31.6340, lon=74.8723,
           bounding_box=BoundingBox(min_lat=31.55, max_lat=31.72, min_lon=74.79, max_lon=74.96)),
    Region(id="delhi_ncr", name="Delhi NCR", lat=28.7041, lon=77.1025,
           bounding_box=BoundingBox(min_lat=28.40, max_lat=28.90, min_lon=76.85, max_lon=77.35)),
]

DETAILED_LOCATIONS = [
    DetailedLocation(id="sector_17", region_id="chandigarh", name="Sector 17", lat=30.7410, lon=76.7822),
    DetailedLocation(id="sector_22", region_id="chandigarh", name="Sector 22", lat=30.7295, lon=76.7770),
    DetailedLocation(id="model_town", region_id="ludhiana", name="Model Town", lat=30.9086, lon=75.8420),
    DetailedLocation(id="hall_bazaar", region_id="amritsar", name="Hall Bazaar", lat=31.6280, lon=74.8760),
    DetailedLocation(id="connaught_place", region_id="delhi_ncr", name="Connaught Place", lat=28.6315, lon=77.2167),
]

PLATFORMS = ["Encrypted Forum Z", "Telegram", "AlphaBay (Reborn)", "Silk Route 3.0", "Genesis Market"]


# ---------------------------------------------------------------------------
# Entities (Piece: alias clusters — easy / medium / hard-decoy)
# ---------------------------------------------------------------------------

entities: list[Entity] = []

# --- Cluster 1: EASY pair — same suspect, near-identical username, same
# platform pattern, overlapping active hours. Should score high on almost
# any similarity method (even plain string matching).
entities.append(Entity(
    id="suspect_1", type=EntityType.suspect, identifier="abc123",
    platform="Encrypted Forum Z", display_name="abc123",
    bio="Reliable seller, fast shipping, ask about bulk.",
    location="Chandigarh", created_at=_iso_minus(days=200),
))
entities.append(Entity(
    id="account_1a", type=EntityType.account, identifier="123_abc",
    platform="Telegram", display_name="123_abc",
    bio="Reliable seller, fast shipping, ask about bulk.",
    location="Chandigarh", created_at=_iso_minus(days=190),
))

# --- Cluster 2: MEDIUM pair — same suspect, DIFFERENT username, only
# findable via shared wallet or bio phrasing, not username matching.
entities.append(Entity(
    id="suspect_2", type=EntityType.suspect, identifier="nightowl_88",
    platform="Encrypted Forum Z", display_name="nightowl_88",
    bio="Trusted vendor since 2019. No scams, no refunds.",
    location="Ludhiana", created_at=_iso_minus(days=400),
))
entities.append(Entity(
    id="account_2a", type=EntityType.account, identifier="darkraven",
    platform="Telegram", display_name="darkraven",
    bio="Trusted vendor since 2019, no scams and no refunds ever.",
    location="Ludhiana", created_at=_iso_minus(days=395),
))

# --- Cluster 3: HARD DECOY — similar-looking usernames that are NOT the
# same person. Tests that scoring doesn't just fuzzy-match strings.
entities.append(Entity(
    id="suspect_3", type=EntityType.suspect, identifier="john123",
    platform="Encrypted Forum Z", display_name="john123",
    bio="New here, looking for good deals.",
    location="Amritsar", created_at=_iso_minus(days=30),
))
entities.append(Entity(
    id="account_3a", type=EntityType.account, identifier="john124",
    platform="Genesis Market", display_name="john124",
    bio="Selling old electronics, unrelated to any of this.",
    location="Delhi NCR", created_at=_iso_minus(days=800),
))

# --- Wallets (~15). One deliberately becomes the anomaly-burst wallet,
# one becomes the bridge entity, a couple stay isolated noise.
WALLET_COUNT = 15
for i in range(1, WALLET_COUNT + 1):
    entities.append(Entity(
        id=f"wallet_{i}", type=EntityType.wallet, identifier=f"bc1q{'x' * (6+i)}{i}",
        platform="Blockchain", display_name=f"Wallet {i}",
        location=None, created_at=_iso_minus(days=random.randint(30, 500)),
    ))

# --- Accounts (~10 total: 2 real aliases + 1 decoy already added above = 3;
# add 7 more as unrelated noise accounts).
for i in range(1, 8):
    entities.append(Entity(
        id=f"account_noise_{i}", type=EntityType.account,
        identifier=f"user_{random.randint(1000,9999)}",
        platform=random.choice(PLATFORMS),
        location=random.choice(["Chandigarh", "Ludhiana", "Amritsar", "Delhi NCR", None]),
        created_at=_iso_minus(days=random.randint(10, 600)),
    ))

# --- Markets (3)
for mkt_id, name in [("mkt_alpha", "AlphaBay (Reborn)"), ("mkt_silk", "Silk Route 3.0"), ("mkt_genesis", "Genesis Market")]:
    entities.append(Entity(
        id=mkt_id, type=EntityType.market, identifier=name,
        platform=name, display_name=name, created_at=_iso_minus(days=600),
    ))

# --- A few extra independent suspects as graph/behavioral noise, no
# planted pattern attached to them.
for i in range(4, 7):
    entities.append(Entity(
        id=f"suspect_{i}", type=EntityType.suspect, identifier=f"vendor_{i}{i}",
        platform=random.choice(PLATFORMS), location=random.choice(["Chandigarh", "Ludhiana", "Amritsar", "Delhi NCR"]),
        created_at=_iso_minus(days=random.randint(50, 700)),
    ))


ENTITY_IDS_BY_TYPE = {
    "suspect": [e.id for e in entities if e.type == EntityType.suspect],
    "wallet": [e.id for e in entities if e.type == EntityType.wallet],
    "account": [e.id for e in entities if e.type == EntityType.account],
    "market": [e.id for e in entities if e.type == EntityType.market],
}


# ---------------------------------------------------------------------------
# Observations (Piece: geographic hot/cold pattern)
# ---------------------------------------------------------------------------

observations: list[Observation] = []
_obs_counter = 0

ACTIVITY_TYPES = ["listing_post", "message", "login", "transfer_check"]

# ~40% of observations concentrated in Chandigarh / Sector 17 -> the
# obvious hotspot. Rest thinly spread across the other 3 regions as
# background noise. A handful with no location at all, to exercise the
# null-handling cleanup step we agreed on rather than just writing it.

all_entity_ids = [e.id for e in entities]
TOTAL_OBSERVATIONS = 220

for _ in range(TOTAL_OBSERVATIONS):
    _obs_counter += 1
    entity_id = random.choice(all_entity_ids)
    roll = random.random()

    if roll < 0.40:
        region, lat, lon = "chandigarh", 30.7410 + random.uniform(-0.01, 0.01), 76.7822 + random.uniform(-0.01, 0.01)
    elif roll < 0.55:
        region, lat, lon = "ludhiana", 30.9010 + random.uniform(-0.03, 0.03), 75.8573 + random.uniform(-0.03, 0.03)
    elif roll < 0.68:
        region, lat, lon = "amritsar", 31.6340 + random.uniform(-0.03, 0.03), 74.8723 + random.uniform(-0.03, 0.03)
    elif roll < 0.85:
        region, lat, lon = "delhi_ncr", 28.7041 + random.uniform(-0.1, 0.1), 77.1025 + random.uniform(-0.1, 0.1)
    else:
        region, lat, lon = None, None, None  # deliberately unlocated

    observations.append(Observation(
        id=f"obs_{_obs_counter}",
        entity_id=entity_id,
        source=random.choice(PLATFORMS),
        timestamp=_iso_minus(days=random.randint(0, 180), hours=random.randint(0, 23)),
        latitude=lat, longitude=lon, region=region,
        activity_type=random.choice(ACTIVITY_TYPES),
        risk_signal=random.choice([None, None, None, "restricted_keyword_match"]),
    ))


# ---------------------------------------------------------------------------
# Transactions (Piece: anomaly burst + new-counterparty spike + graph shape)
# ---------------------------------------------------------------------------

transactions: list[Transaction] = []
_tx_counter = 0


def _add_tx(source, target, amount, currency, timestamp):
    global _tx_counter
    _tx_counter += 1
    transactions.append(Transaction(
        id=f"tx_{_tx_counter}", source_entity=source, target_entity=target,
        amount=amount, currency=currency, timestamp=timestamp,
    ))


# --- Baseline normal activity: every suspect/account trades with a
# handful of wallets/markets, spread naturally over weeks/months.
suspects_and_accounts = ENTITY_IDS_BY_TYPE["suspect"] + ENTITY_IDS_BY_TYPE["account"]
wallets = ENTITY_IDS_BY_TYPE["wallet"]
markets = ENTITY_IDS_BY_TYPE["market"]

for actor in suspects_and_accounts:
    counterparties = random.sample(wallets, k=min(3, len(wallets)))
    for cp in counterparties:
        _add_tx(actor, cp, round(random.uniform(0.01, 0.8), 4), "BTC",
                _iso_minus(days=random.randint(5, 150), hours=random.randint(0, 23)))
    if random.random() < 0.5:
        _add_tx(actor, random.choice(markets), round(random.uniform(0.01, 0.5), 4), "BTC",
                _iso_minus(days=random.randint(5, 150)))

# --- Planted anomaly #1: transaction-frequency burst.
# wallet_5 gets 14 transactions with the SAME counterparty (wallet_9)
# within a single hour. Matches the workplan's own example pattern.
burst_start = _iso_minus(days=2, hours=3)
for i in range(14):
    _add_tx("wallet_5", "wallet_9", round(random.uniform(0.05, 0.2), 4), "BTC",
            burst_start + timedelta(minutes=i * 4))

# --- Planted anomaly #2: new-counterparty spike (different SHAPE of
# anomaly — not frequency, but a sudden burst of brand-new relationships).
# suspect_2 (normally trades with the same 3 wallets) suddenly transacts
# with 5 wallets they've never touched before, all within one day.
spike_day = _iso_minus(days=1)
new_counterparties = random.sample(
    [w for w in wallets if w not in ("wallet_5", "wallet_9")], k=5
)
for i, cp in enumerate(new_counterparties):
    _add_tx("suspect_2", cp, round(random.uniform(0.1, 1.0), 4), "BTC",
            spike_day + timedelta(hours=i * 2))

# --- Planted graph structure: bridge entity.
# wallet_10 connects Cluster 1 (suspect_1 + account_1a) to Cluster 2
# (suspect_2 + account_2a) — the only path between the two clusters, so
# betweenness centrality has something real to find.
_add_tx("suspect_1", "wallet_10", 0.3, "BTC", _iso_minus(days=40))
_add_tx("account_1a", "wallet_10", 0.15, "BTC", _iso_minus(days=38))
_add_tx("wallet_10", "suspect_2", 0.25, "BTC", _iso_minus(days=35))
_add_tx("wallet_10", "account_2a", 0.2, "BTC", _iso_minus(days=33))

# --- Dense cluster reinforcement: tie each alias to its "real" suspect's
# other wallets, so community detection has an obvious tight-knit group.
_add_tx("suspect_1", "wallet_1", 0.4, "BTC", _iso_minus(days=60))
_add_tx("account_1a", "wallet_1", 0.1, "BTC", _iso_minus(days=58))
_add_tx("suspect_1", "wallet_2", 0.2, "BTC", _iso_minus(days=55))
_add_tx("account_1a", "wallet_2", 0.05, "BTC", _iso_minus(days=53))

_add_tx("suspect_2", "wallet_3", 0.3, "BTC", _iso_minus(days=70))
_add_tx("account_2a", "wallet_3", 0.1, "BTC", _iso_minus(days=68))
_add_tx("suspect_2", "wallet_4", 0.15, "BTC", _iso_minus(days=65))
_add_tx("account_2a", "wallet_4", 0.05, "BTC", _iso_minus(days=63))

# --- Isolated / low-degree noise: wallet_14 and wallet_15 get exactly
# one transaction each, connected to nothing else — pure graph noise.
_add_tx("suspect_3", "wallet_14", 0.02, "BTC", _iso_minus(days=90))
_add_tx("account_3a", "wallet_15", 0.01, "BTC", _iso_minus(days=200))


# ---------------------------------------------------------------------------
# Ground truth — the known "answer key" these patterns encode.
# Nothing downstream should read this directly; it's for evaluating
# whether our detection logic finds what we planted.
# ---------------------------------------------------------------------------

GROUND_TRUTH = {
    "alias_clusters": {
        "easy": {"same_entity": ["suspect_1", "account_1a"], "difficulty": "near-identical username, same bio, overlapping activity"},
        "medium": {"same_entity": ["suspect_2", "account_2a"], "difficulty": "different username, shared wallet + bio phrasing only"},
        "decoy": {"same_entity": False, "entities": ["suspect_3", "account_3a"], "difficulty": "similar-looking usernames, NOT the same person"},
    },
    "anomaly_burst": {"entity": "wallet_5", "counterparty": "wallet_9", "pattern": "14 tx within 1 hour"},
    "new_counterparty_spike": {"entity": "suspect_2", "pattern": "5 brand-new counterparties within 1 day"},
    "bridge_entity": {"entity": "wallet_10", "connects": ["suspect_1 cluster", "suspect_2 cluster"]},
    "isolated_noise": ["wallet_14", "wallet_15"],
    "geographic_hotspot": {"region": "chandigarh", "share": "~40% of observations"},
}


if __name__ == "__main__":
    print(f"entities: {len(entities)}")
    print(f"observations: {len(observations)}")
    print(f"transactions: {len(transactions)}")
    print(f"regions: {len(REGIONS)}, detailed_locations: {len(DETAILED_LOCATIONS)}")