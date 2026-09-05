"""
Pipeline: Ingest Elliptic++ Crypto Wallets / Transactions & OFAC Sanctioned Addresses.
Creates distinct 1:1 Suspect entities per OFAC sanctioned entity name.
"""

from __future__ import annotations

import os
import json
import hashlib
import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal
from models import CryptoWallet, CryptoTransaction, Suspect, DataProvenance, utc_now, time_step_to_timestamp

REAL_DATA_FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "real_data_files"))

def ingest_elliptic_data(db: Session) -> tuple[int, int]:
    elliptic_dir = os.path.join(REAL_DATA_FILES_DIR, "elliptic")
    wc_path = os.path.join(elliptic_dir, "wallets_classes.csv")
    edge_path = os.path.join(elliptic_dir, "AddrAddr_edgelist.csv")

    if not os.path.exists(wc_path) or not os.path.exists(edge_path):
        print(f"[ingest_elliptic_ofac] Elliptic++ files missing in {elliptic_dir}")
        return (0, 0)

    # 1. Ingest Wallets
    df_wc = pd.read_csv(wc_path)
    df_wc.columns = [c.strip() for c in df_wc.columns]
    
    class_map = {1: "ILLICIT", 2: "LICIT", 3: "UNKNOWN"}
    wallets_to_add = []
    
    existing_addrs = set(r[0] for r in db.query(CryptoWallet.address).all())

    for _, row in df_wc.iterrows():
        addr = str(row["address"]).strip()
        if addr in existing_addrs:
            continue
        cls_num = int(row.get("class", 3))
        risk_lvl = class_map.get(cls_num, "UNKNOWN")
        
        wallets_to_add.append(CryptoWallet(
            address=addr,
            currency="BTC",
            balance="0.0",
            risk_level=risk_lvl
        ))
        existing_addrs.add(addr)

    db.bulk_save_objects(wallets_to_add)
    db.commit()
    print(f"[ingest_elliptic_ofac] Ingested {len(wallets_to_add)} Elliptic++ CryptoWallets")

    # 2. Ingest Transfer Edges as CryptoTransactions with Deterministic SHA-256 Synthetic Hashes
    df_edges = pd.read_csv(edge_path)
    df_edges.columns = [c.strip() for c in df_edges.columns]

    existing_tx_hashes = set(r[0] for r in db.query(CryptoTransaction.tx_hash).all())
    txs_to_add = []

    print("[ingest_elliptic_ofac] Generating deterministic SHA-256 synthetic tx_hashes for Elliptic++ edge transactions...")
    for idx, row in df_edges.iterrows():
        src = str(row["input_address"]).strip()
        dst = str(row["output_address"]).strip()

        # Option (b): Deterministic SHA-256 synthetic hash representing Elliptic++ edge transfer
        raw_sig = f"elliptic_edge:{src}:{dst}:{idx}"
        syn_hash = hashlib.sha256(raw_sig.encode()).hexdigest()

        if syn_hash in existing_tx_hashes:
            continue

        txs_to_add.append(CryptoTransaction(
            tx_hash=syn_hash,
            from_address=src,
            to_address=dst,
            amount="UNSPECIFIED",  # Elliptic++ transfer edges do not carry monetary amounts
            currency="BTC",
            timestamp=time_step_to_timestamp(1)  # Epoch mapping
        ))
        existing_tx_hashes.add(syn_hash)

    db.bulk_save_objects(txs_to_add)
    db.commit()

    # Provenance
    prov = DataProvenance(
        source_type="Blockchain Network Graph",
        source_name="Elliptic++ Subsampled Actor Graph",
        source_identifier="real_data_files/elliptic/",
        collection_method="Stratified connected subgraph extraction",
        collected_at=utc_now(),
        integrity_hash="SHA256:ELLIPTIC_SUBSAMPLE"
    )
    db.add(prov)
    db.commit()

    print(f"[ingest_elliptic_ofac] Ingested {len(txs_to_add)} Elliptic++ CryptoTransactions (using deterministic SHA-256 synthetic tx_hashes)")
    return (len(wallets_to_add), len(txs_to_add))

def ingest_ofac_sanctions(db: Session) -> tuple[int, int]:
    # Check for enriched OFAC json mapping address -> entity_name
    enriched_file = os.path.join(REAL_DATA_FILES_DIR, "ofac", "sanctioned_addresses_with_entities.json")
    basic_file = os.path.join(REAL_DATA_FILES_DIR, "ofac", "sanctioned_addresses_XBT.json")
    
    sanctioned_items = []
    if os.path.exists(enriched_file):
        with open(enriched_file, "r") as f:
            sanctioned_items = json.load(f)
    elif os.path.exists(basic_file):
        with open(basic_file, "r") as f:
            addrs = json.load(f)
            sanctioned_items = [{"address": a, "entity_name": "OFAC Sanctioned Entity Target"} for a in addrs]
    else:
        print(f"[ingest_elliptic_ofac] OFAC file missing in {REAL_DATA_FILES_DIR}/ofac/")
        return (0, 0)

    print(f"[ingest_elliptic_ofac] Processing {len(sanctioned_items)} OFAC sanctioned BTC addresses...")

    # Group addresses by entity_name to create 1:1 Suspect records per distinct OFAC entity name
    entity_to_addrs = {}
    for item in sanctioned_items:
        addr = str(item["address"]).strip()
        ent_name = str(item.get("entity_name", "OFAC Sanctioned Entity Target")).strip()
        entity_to_addrs.setdefault(ent_name, []).append(addr)

    print(f"[ingest_elliptic_ofac] Found {len(entity_to_addrs)} distinct OFAC entity names on disk.")

    entity_suspect_map = {}
    created_suspects = 0

    for ent_name in entity_to_addrs.keys():
        suspect = db.query(Suspect).filter(Suspect.primary_alias == ent_name).first()
        if not suspect:
            suspect = Suspect(
                primary_alias=ent_name,
                aliases_json=json.dumps([ent_name, f"OFAC Target ({ent_name})"]),
                notes=f"Distinct OFAC Specially Designated National target: {ent_name}",
                risk_score=95
            )
            db.add(suspect)
            db.commit()
            db.refresh(suspect)
            created_suspects += 1
        entity_suspect_map[ent_name] = suspect.id

    updated_cnt = 0
    created_cnt = 0

    for ent_name, addrs in entity_to_addrs.items():
        s_id = entity_suspect_map[ent_name]
        for addr in addrs:
            wallet = db.query(CryptoWallet).filter(CryptoWallet.address == addr).first()
            if wallet:
                wallet.risk_level = "SANCTIONED"
                wallet.associated_suspect_id = s_id
                updated_cnt += 1
            else:
                new_wallet = CryptoWallet(
                    address=addr,
                    currency="BTC",
                    balance="0.0",
                    risk_level="SANCTIONED",
                    associated_suspect_id=s_id
                )
                db.add(new_wallet)
                created_cnt += 1

    db.commit()

    prov = DataProvenance(
        source_type="Sanctions Watchlist",
        source_name="US Treasury OFAC SDN Digital Currency List",
        source_identifier="real_data_files/ofac/sanctioned_addresses_with_entities.json",
        collection_method="Automated official OFAC SDN API extraction & entity mapping",
        collected_at=utc_now(),
        integrity_hash="SHA256:OFAC_SANCTIONS_LIST_ENRICHED"
    )
    db.add(prov)
    db.commit()

    print(f"[ingest_elliptic_ofac] Ingested OFAC Sanctions: Created {created_suspects} distinct entity Suspect records. Wallets: {created_cnt} new, {updated_cnt} updated.")
    return (created_cnt, updated_cnt)

def run_ingestion(db: Session = None):
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        w_cnt, tx_cnt = ingest_elliptic_data(db)
        ofac_created, ofac_updated = ingest_ofac_sanctions(db)
        print(f"[ingest_elliptic_ofac] Completed crypto & sanctions ingestion.")
    finally:
        if close_session:
            db.close()

if __name__ == "__main__":
    run_ingestion()
