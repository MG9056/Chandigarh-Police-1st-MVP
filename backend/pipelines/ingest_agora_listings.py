"""
Pipeline: Ingest Agora Darknet Marketplace Listings into darknet_listings.
Creates 1:1 Suspect entities per distinct vendor_alias and links listings via associated_suspect_id.
"""

from __future__ import annotations

import os
import json
import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal
from models import DarknetListing, Suspect, DataProvenance, utc_now

REAL_DATA_FILES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "real_data_files"))

def ingest_agora_sample(db: Session) -> int:
    path = os.path.join(REAL_DATA_FILES_DIR, "listings", "agora_sample.csv")
    if not os.path.exists(path):
        print(f"[ingest_agora] Skipping {path} (file not found)")
        return 0

    print(f"[ingest_agora] Ingesting Agora listings from {path}...")
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    # Create 1:1 Suspect record per distinct vendor_alias
    distinct_vendors = sorted(list(set(df["Vendor"].dropna().astype(str).str.strip())))
    print(f"[ingest_agora] Found {len(distinct_vendors)} distinct vendor_alias values in sample.")

    vendor_suspect_map = {}
    created_suspects = 0

    for v_alias in distinct_vendors:
        suspect = db.query(Suspect).filter(Suspect.primary_alias == v_alias).first()
        if not suspect:
            suspect = Suspect(
                primary_alias=v_alias,
                aliases_json=json.dumps([v_alias, f"AgoraVendor_{v_alias}"]),
                notes=f"Vendor alias extracted from Agora Darknet Marketplace crawl.",
                risk_score=75
            )
            db.add(suspect)
            db.commit()
            db.refresh(suspect)
            created_suspects += 1
        vendor_suspect_map[v_alias] = suspect.id

    # Deduplication: load existing (vendor_alias, title) pairs so repeated
    # runs of this function (triggered by db_sync.py) never create duplicates.
    existing_keys: set[tuple[str, str]] = set(
        db.query(DarknetListing.vendor_name, DarknetListing.title)
        .filter(DarknetListing.marketplace == "Agora")
        .all()
    )
    print(f"[ingest_agora] {len(existing_keys)} Agora listings already in DB — will skip those.")

    listings = []
    for idx, row in df.iterrows():
        vendor = str(row.get("Vendor", "UnknownVendor")).strip()
        category = str(row.get("Category", "Uncategorized")).strip()
        title = str(row.get("Item", f"Listing #{idx+1}")).strip()
        price = str(row.get("Price", "0.0 BTC")).strip()
        location = str(row.get("Origin", "Worldwide")).strip()

        # Skip if this (vendor_alias, title) pair is already in DB
        if (vendor, title) in existing_keys:
            continue

        suspect_id = vendor_suspect_map.get(vendor)

        listings.append(DarknetListing(
            listing_id=f"agora-{idx + 1000}",
            title=title,
            description=f"Agora darknet listing by vendor {vendor}. Category: {category}. Shipping from {location}.",
            vendor_name=vendor,
            marketplace="Agora",
            drug_category=category,
            price=price,
            currency="BTC",
            location=location,
            url=f"http://agora2745onion.onion/item/{idx+1000}",
            scraped_at=utc_now(),
            associated_suspect_id=suspect_id
        ))
        existing_keys.add((vendor, title))  # prevent intra-batch duplicates too

    if listings:
        db.bulk_save_objects(listings)

    prov = DataProvenance(
        source_type="Darknet Marketplace",
        source_name="Agora Darknet Marketplace Dataset (2014-2015)",
        source_identifier="real_data_files/listings/agora_sample.csv",
        collection_method="Stratified category subsample of historical market crawl",
        collected_at=utc_now(),
        integrity_hash="SHA256:AGORA_LISTINGS_SAMPLE"
    )
    db.add(prov)
    db.commit()

    print(f"[ingest_agora] Successfully ingested {len(listings)} new DarknetListing records (linked to {created_suspects} new vendor Suspects).")
    return len(listings)

def run_ingestion(db: Session = None):
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        cnt = ingest_agora_sample(db)
        print(f"[ingest_agora] Ingestion complete. Total listings: {cnt}")
    finally:
        if close_session:
            db.close()

if __name__ == "__main__":
    run_ingestion()
