"""
db_sync.py
──────────
Re-ingestion bridge: reads from the fixed CSV/JSON dataset files and calls
the existing ingestion functions to bring darknight.db into sync.

Two callers:
  A) crawler_to_dataset_updater.py — after each poll cycle that wrote
     at least one new row to a CSV/JSON file.
  B) sources.py (POST /api/sources/{id}/stop) — as a final catch-up
     before a crawl session ends.

Design:
  • Idempotent — all ingestion functions have been hardened to dedup before
    inserting (see ingest_agora_listings.py and ingest_elliptic_ofac.py).
    Running this multiple times over the same CSV produces no duplicate rows.
  • Scoped — only touches the three fixed dataset files used in Track 1.
    Does NOT scan the project directory, does NOT touch Daksh/network CSVs
    (those files don't exist in-repo and the ingest function always returns 0).
  • Logged — logs trigger reason, rows found in each CSV, and rows actually
    written to DB (delta = found - already-existing).
"""

from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy.orm import Session

logger = logging.getLogger("db_sync")

TriggerReason = Literal["poll_cycle_update", "crawler_stopped"]


def run_dataset_sync(db: Session, reason: TriggerReason) -> dict[str, int]:
    """
    Calls each ingestion function in sequence and returns a dict of
    {table_name: rows_written_to_db}.

    `reason` is used only for logging.
    """
    from pipelines.ingest_agora_listings import ingest_agora_sample
    from pipelines.ingest_elliptic_ofac import ingest_elliptic_data, ingest_ofac_sanctions

    logger.info("[db_sync] Re-ingestion triggered — reason: %s", reason)

    results: dict[str, int] = {}

    # --- Agora listings → darknet_listings + suspects ----------------------
    try:
        agora_written = ingest_agora_sample(db)
        results["darknet_listings"] = agora_written
        logger.info(
            "[db_sync] (%s) agora -> darknet_listings: %d new rows written",
            reason, agora_written,
        )
    except Exception as exc:
        logger.error("[db_sync] agora re-ingest failed: %s", exc, exc_info=True)
        results["darknet_listings"] = 0

    # --- Elliptic++ wallets + edges → crypto_wallets + crypto_transactions --
    try:
        wallets_written, txs_written = ingest_elliptic_data(db)
        results["crypto_wallets"]      = wallets_written
        results["crypto_transactions"] = txs_written
        logger.info(
            "[db_sync] (%s) elliptic -> crypto_wallets: %d new, crypto_transactions: %d new",
            reason, wallets_written, txs_written,
        )
    except Exception as exc:
        logger.error("[db_sync] elliptic re-ingest failed: %s", exc, exc_info=True)
        results["crypto_wallets"] = 0
        results["crypto_transactions"] = 0

    # --- OFAC → suspects + crypto_wallets (SANCTIONED tag) -----------------
    try:
        ofac_created, ofac_updated = ingest_ofac_sanctions(db)
        results["ofac_wallets_new"]     = ofac_created
        results["ofac_wallets_updated"] = ofac_updated
        logger.info(
            "[db_sync] (%s) ofac -> suspects/wallets: %d new wallets, %d updated to SANCTIONED",
            reason, ofac_created, ofac_updated,
        )
    except Exception as exc:
        logger.error("[db_sync] ofac re-ingest failed: %s", exc, exc_info=True)
        results["ofac_wallets_new"] = 0
        results["ofac_wallets_updated"] = 0

    total_new = sum(
        v for k, v in results.items()
        if k not in ("ofac_wallets_updated",)  # updates aren't "new rows"
    )
    logger.info(
        "[db_sync] Re-ingestion complete (reason=%s). Total new DB rows: %d. Breakdown: %s",
        reason, total_new, results,
    )
    return results
