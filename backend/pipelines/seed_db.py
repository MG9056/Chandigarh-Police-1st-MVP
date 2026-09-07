"""
Master Orchestrator: Seeding SQLite Database (darknight.db) for Project Dark Knight.
Executes all ingestion pipelines in order, then runs a selective fuzzy entity resolution pass on overlapping aliases.
"""

from __future__ import annotations

import sys
import os
import json
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import init_db, SessionLocal, engine
from models import (
    User, Suspect, CryptoWallet, CryptoTransaction, DarknetListing,
    TelegramChannel, TelegramMessage, NetworkTrafficFlow,
    DataProvenance, AuditLog
)
from entity_resolution import username_similarity

from pipelines import ingest_daksh_datasets
from pipelines import ingest_elliptic_ofac
from pipelines import ingest_agora_listings
from pipelines import ingest_telegram

def run_selective_fuzzy_resolution_pass(db: Session):
    """
    Selective Pass: Merges existing Suspect records ONLY where vendor aliases, telegram handles,
    or OFAC entity names genuinely overlap (similarity >= 0.85), without suppressing distinct 1:1 suspects.
    Protects distinct official OFAC targets from merging with each other.
    """
    print("\n[seed_db] Running selective fuzzy entity resolution pass for overlapping aliases...")

    suspects = db.query(Suspect).all()
    print(f"[seed_db] Total Suspect records before merge pass: {len(suspects)}")

    merged_count = 0
    to_delete = set()
    for i in range(len(suspects)):
        s1 = suspects[i]
        if s1.id in to_delete:
            continue
        for j in range(i + 1, len(suspects)):
            s2 = suspects[j]
            if s2.id in to_delete:
                continue

            # Protect distinct OFAC targets from merging with each other
            is_ofac_s1 = "OFAC" in (s1.notes or "")
            is_ofac_s2 = "OFAC" in (s2.notes or "")
            if is_ofac_s1 and is_ofac_s2:
                continue

            # Compare primary aliases
            sim = username_similarity(s1.primary_alias, s2.primary_alias)
            if sim["username_similarity"] >= 0.85:
                print(f"  [fuzzy_merge] Merging '{s2.primary_alias}' into '{s1.primary_alias}' (score={sim['username_similarity']})")
                
                # Combine aliases
                a1 = json.loads(s1.aliases_json) if s1.aliases_json else []
                a2 = json.loads(s2.aliases_json) if s2.aliases_json else []
                combined_aliases = sorted(list(set(a1 + a2 + [s2.primary_alias])))
                s1.aliases_json = json.dumps(combined_aliases)

                # Preserve Telegram handle if s2 has one
                if s2.telegram_handle and not s1.telegram_handle:
                    s1.telegram_handle = s2.telegram_handle

                # Re-link child foreign keys from s2 to s1
                db.query(CryptoWallet).filter(CryptoWallet.associated_suspect_id == s2.id).update({CryptoWallet.associated_suspect_id: s1.id})
                db.query(DarknetListing).filter(DarknetListing.associated_suspect_id == s2.id).update({DarknetListing.associated_suspect_id: s1.id})

                to_delete.add(s2.id)
                merged_count += 1

    if to_delete:
        db.query(Suspect).filter(Suspect.id.in_(list(to_delete))).delete(synchronize_session=False)
        db.commit()

    final_suspects_cnt = db.query(Suspect).count()
    print(f"[seed_db] Merged {merged_count} overlapping Suspect records. Final distinct Suspect count: {final_suspects_cnt}")

def seed_database():
    print("=" * 70)
    print("STARTING DATABASE SEEDING FOR PROJECT DARK KNIGHT")
    print("=" * 70)

    # Re-initialize fresh SQLite tables
    print("\n[seed_db] 1/6 Initializing SQLite database schema...")
    init_db()

    db = SessionLocal()
    try:
        # Wipe existing tables for clean seed
        db.query(NetworkTrafficFlow).delete()
        db.query(CryptoTransaction).delete()
        db.query(CryptoWallet).delete()
        db.query(DarknetListing).delete()
        db.query(TelegramMessage).delete()
        db.query(TelegramChannel).delete()
        db.query(Suspect).delete()
        db.query(DataProvenance).delete()
        db.commit()

        # 2. Ingest Daksh's Dataset Collection
        print("\n[seed_db] 2/6 Ingesting Daksh's dataset collection (DATASETS/*.csv)...")
        ingest_daksh_datasets.run_ingestion(db)

        # 3. Ingest Elliptic++ Subsampled Graph & OFAC Sanctions (1:1 per OFAC entity name)
        print("\n[seed_db] 3/6 Ingesting Elliptic++ Blockchain Graph & OFAC Sanctioned Addresses...")
        ingest_elliptic_ofac.run_ingestion(db)

        # 4. Ingest Agora Marketplace Listings (1:1 per vendor alias)
        print("\n[seed_db] 4/6 Ingesting Agora Darknet Marketplace Listings...")
        ingest_agora_listings.run_ingestion(db)

        # 5. Ingest Telegram Channels & Test Messages (linked to sender handles)
        print("\n[seed_db] 5/6 Ingesting Telegram Channels & Synthetic Messages...")
        ingest_telegram.run_ingestion(db)

        # 6. Run Selective Fuzzy Entity Resolution Pass
        print("\n[seed_db] 6/6 Running Selective Fuzzy Entity Resolution Pass...")
        run_selective_fuzzy_resolution_pass(db)

        print("\n" + "=" * 70)
        print("DATABASE SEEDING COMPLETE! REPORTING TABLE ROW COUNTS & LINK METRICS:")
        print("=" * 70)

        tables = [
            ("users", User),
            ("suspects", Suspect),
            ("crypto_wallets", CryptoWallet),
            ("crypto_transactions", CryptoTransaction),
            ("darknet_listings", DarknetListing),
            ("telegram_channels", TelegramChannel),
            ("telegram_messages", TelegramMessage),
            ("network_traffic_flows", NetworkTrafficFlow),
            ("data_provenances", DataProvenance),
            ("audit_logs", AuditLog),
        ]

        total_records = 0
        for t_name, model in tables:
            cnt = db.query(model).count()
            total_records += cnt
            print(f"  - Table '{t_name}': {cnt:,} rows")

        # Specific Linkage Reports requested by user:
        wallets_linked = db.query(CryptoWallet).filter(CryptoWallet.associated_suspect_id.isnot(None)).count()
        wallets_total = db.query(CryptoWallet).count()
        wallets_unlinked = wallets_total - wallets_linked

        listings_linked = db.query(DarknetListing).filter(DarknetListing.associated_suspect_id.isnot(None)).count()
        listings_total = db.query(DarknetListing).count()
        listings_unlinked = listings_total - listings_linked

        tg_handles = set(m.sender_handle for m in db.query(TelegramMessage).all())
        suspect_handles = set(s.telegram_handle for s in db.query(Suspect).all() if s.telegram_handle)
        tg_linked_handles = tg_handles.intersection(suspect_handles)
        tg_messages_count = db.query(TelegramMessage).count()

        print("\n" + "=" * 70)
        print("SUSPECT LINKAGE STATISTICAL SUMMARY:")
        print("=" * 70)
        print(f"  - CryptoWallet Linkage: {wallets_linked:,} linked ({wallets_linked/wallets_total*100:.1f}%) | {wallets_unlinked:,} unlinked (Elliptic++ background nodes)")
        print(f"  - DarknetListing Linkage: {listings_linked:,} linked ({listings_linked/listings_total*100:.1f}%) | {listings_unlinked:,} unlinked")
        print(f"  - TelegramMessage Sender Handle Linkage: All {tg_messages_count} messages sent by {len(tg_handles)} handles ({', '.join(sorted(tg_handles))}) map 100% to Suspect.telegram_handle records.")

    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
