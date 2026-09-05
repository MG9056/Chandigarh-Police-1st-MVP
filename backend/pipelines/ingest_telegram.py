"""
Pipeline: Ingest Telegram Channels & Rich Synthetic Messages with Real Intelligence Cross-Referencing.
Generates 10 channels, 175 procedural non-persuasive test messages cross-referenced to
real DarknetListing and CryptoWallet records in the database, and links sender handles to Suspect entities.
"""

from __future__ import annotations

import os
import sys
import json
import re
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import SessionLocal
from models import TelegramChannel, TelegramMessage, DarknetListing, CryptoWallet, Suspect, DataProvenance, utc_now
from real_data.config import BTC_ADDRESS_REGEX
from entity_resolution import username_similarity

BTC_RE = re.compile(BTC_ADDRESS_REGEX)

DRUG_KEYWORDS = [
    "opioids", "cannabis", "stimulants", "heroin", "synthetic",
    "fentanyl", "tramadol", "mdma", "prescription", "cocaine",
    "opiates", "psychedelics"
]

LINKED_TEMPLATES = [
    # Stock & Availability (Linked to Listing)
    "Inventory Notice: Batch status for catalog entry '{title}' by vendor '{vendor}' updated to ACTIVE. Category: {drug_category}.",
    "Marketplace Log: Catalog item '{title}' (Vendor: '{vendor}') confirmed available. Shipping origin: {location}.",
    "System Audit: Verified listing '{title}' under category '{drug_category}' for vendor alias '{vendor}'. Listed price: {price}.",
    
    # Payment & Wallet Routing (Linked to Wallet & Listing)
    "Payment Routing Log: Direct settlement request for item '{title}' ({price}). Destination wallet address: {wallet}. Vendor: '{vendor}'.",
    "Transaction Verification: Settlement of {price} for catalog reference '{title}' queued to deposit address {wallet}.",
    "Escrow Log: Funds cleared for order item '{title}' by vendor '{vendor}'. Output transaction sent to address {wallet}.",
    
    # Shipping & Logistics (Linked to Listing)
    "Logistics Update: Batch shipment for listing '{title}' by vendor '{vendor}' dispatched from {location}. Category: {drug_category}.",
    "Regional Transit Log: Package containing item reference '{title}' cleared transit checkpoint. Origin: {location}.",
    "Dispatch Registry: Item '{title}' (Vendor: '{vendor}') marked in-transit. Reference payment wallet: {wallet}.",
    
    # Vendor Reputation & Alias Cross-Check (Linked to Vendor Alias)
    "Vendor Audit Record: Reputation metrics for vendor alias '{vendor}' verified consistent across marketplace listings.",
    "Catalog Mirror: Vendor '{vendor}' catalog entry '{title}' verified on platform. Associated payment address: {wallet}.",
    "Identity Cross-Check: Alias '{vendor}' confirmed active. Linked listing: '{title}' ({price}).",
    
    # Flagged Wallet & Security Advisories (Linked to Wallet)
    "Network Warning: Suspicious transaction pattern detected on wallet address {wallet}. Address flagged for law enforcement monitoring."
]

FILLER_TEMPLATES = [
    "Security Advisory: Monitored transport routes in Northern region flagged for high law enforcement presence. Exercise operational caution.",
    "System Monitor Notice: Keyword indicator '{keyword}' flagged in automated scan log. Parameter check required.",
    "Operational Check: Telegram relay node #{node_id} status OK. System latency {latency}ms. Active channels monitored.",
    "Channel Sync Log: Multi-platform relay synchronized {count} listing entries across encrypted discussion boards.",
    "Daily Intelligence Summary: Channel message volume normal. 0 dispute escalations logged for observation period.",
    "Protocol Notice: Node security check complete. Encrypted channel routing verified operational.",
    "Dispute Resolution Log: Order #{order_id} buyer inquiry logged. Vendor response pending under standard 48h protocol."
]

def ingest_synthetic_telegram(db: Session) -> tuple[int, int, dict]:
    print("[ingest_telegram] Generating rich Telegram channels & cross-referenced synthetic messages...")

    # Wipe only Telegram tables for clean re-seed
    db.query(TelegramMessage).delete()
    db.query(TelegramChannel).delete()
    db.commit()

    # Query existing real domain records to cross-reference
    real_listings = db.query(DarknetListing).all()
    real_wallets = db.query(CryptoWallet).all()
    existing_suspects = db.query(Suspect).all()

    print(f"[ingest_telegram] Loaded {len(real_listings)} DarknetListings, {len(real_wallets)} CryptoWallets, {len(existing_suspects)} Suspects for cross-referencing.")

    channels_data = [
        {"channel_id": "ch_1001", "channel_name": "@ChandigarhPharmaNet", "description": "Automated regional supply monitoring channel #1", "member_count": 1420},
        {"channel_id": "ch_1002", "channel_name": "@DarkTriadDiscussions", "description": "Encrypted network operational log channel #2", "member_count": 890},
        {"channel_id": "ch_1003", "channel_name": "@EncryptedSupplyNorth", "description": "Northern region vendor coordination desk #3", "member_count": 2150},
        {"channel_id": "ch_1004", "channel_name": "@PharmaTestChannel", "description": "Automated verification & quality check channel #4", "member_count": 640},
        {"channel_id": "ch_1005", "channel_name": "@CryptoDrugDesk", "description": "Cryptocurrency settlement verification channel #5", "member_count": 3100},
        {"channel_id": "ch_1006", "channel_name": "@LogisticsHubNorth", "description": "Regional logistics tracking and dispatch desk #6", "member_count": 1750},
        {"channel_id": "ch_1007", "channel_name": "@EscrowDisputeNotice", "description": "Automated transaction dispute resolution log #7", "member_count": 1120},
        {"channel_id": "ch_1008", "channel_name": "@SecurityAlertsNet", "description": "Law enforcement situational awareness feed #8", "member_count": 2450},
        {"channel_id": "ch_1009", "channel_name": "@MarketplaceRelayCentral", "description": "Multi-market listing mirror and status board #9", "member_count": 1980},
        {"channel_id": "ch_1010", "channel_name": "@VendorReputationRegistry", "description": "Cross-platform vendor alias verification registry #10", "member_count": 1630},
    ]

    channels_map = {}
    for c_info in channels_data:
        ch = TelegramChannel(
            channel_id=c_info["channel_id"],
            channel_name=c_info["channel_name"],
            description=c_info["description"],
            member_count=c_info["member_count"]
        )
        db.add(ch)
        db.commit()
        db.refresh(ch)
        channels_map[c_info["channel_id"]] = ch

    test_handles = [
        "@AlphaNode_CDG", "@NordicVendor", "@PharmaTech_99", "@LogInspector",
        "@TriadRelay", "@DeltaAgent", "@LogisticOps_North", "@SecurityMonitor_CDG",
        "@EscrowAuditor", "@RelayBot_01"
    ]

    # Preferentially match Telegram handles to existing Suspect records
    merged_handles = []
    standalone_handles = []

    for handle in test_handles:
        clean_h = handle.lstrip("@")
        best_suspect = None
        best_score = 0.0

        for s in existing_suspects:
            sim = username_similarity(clean_h, s.primary_alias)
            score = sim["username_similarity"]
            if score > best_score:
                best_score = score
                best_suspect = s

        if best_suspect and best_score >= 0.85:
            if not best_suspect.telegram_handle:
                best_suspect.telegram_handle = handle
            curr_aliases = json.loads(best_suspect.aliases_json) if best_suspect.aliases_json else []
            if handle not in curr_aliases:
                curr_aliases.append(handle)
            if clean_h not in curr_aliases:
                curr_aliases.append(clean_h)
            best_suspect.aliases_json = json.dumps(sorted(list(set(curr_aliases))))
            db.commit()
            merged_handles.append((handle, best_suspect.primary_alias, best_score))
        else:
            suspect = db.query(Suspect).filter((Suspect.telegram_handle == handle) | (Suspect.primary_alias == clean_h)).first()
            if not suspect:
                suspect = Suspect(
                    primary_alias=clean_h,
                    aliases_json=json.dumps([clean_h, handle]),
                    telegram_handle=handle,
                    notes=f"Standalone Telegram active sender handle: {handle}",
                    risk_score=70
                )
                db.add(suspect)
                db.commit()
            standalone_handles.append(handle)

    random.seed(1337)
    messages_to_add = []
    linked_count = 0
    filler_count = 0

    base_time = utc_now() - timedelta(days=30)
    channel_timers = {c["channel_id"]: base_time + timedelta(hours=random.randint(1, 12)) for c in channels_data}

    # Generate 175 messages across the 10 channels
    for i in range(1, 176):
        ch_key = f"ch_10{((i - 1) % 10) + 1:02d}"
        ch_obj = channels_map[ch_key]
        sender = random.choice(test_handles)
        
        # Increment channel timer for chronological order
        channel_timers[ch_key] += timedelta(hours=random.randint(2, 6), minutes=random.randint(0, 59))
        msg_timestamp = channel_timers[ch_key]

        # 52% probability of cross-referencing real DB data (linked message)
        is_linked = (i % 2 == 0) or (random.random() < 0.52)

        if is_linked and real_listings and real_wallets:
            template = random.choice(LINKED_TEMPLATES)
            listing = random.choice(real_listings)
            wallet = random.choice(real_wallets)

            text = template.format(
                title=listing.title,
                vendor=listing.vendor_alias,
                drug_category=listing.drug_category,
                price=listing.price or "0.05 BTC",
                location=listing.location or "Worldwide",
                wallet=wallet.address
            )
            linked_count += 1
        else:
            template = random.choice(FILLER_TEMPLATES)
            text = template.format(
                keyword=random.choice(DRUG_KEYWORDS),
                node_id=random.randint(101, 199),
                latency=random.randint(15, 85),
                count=random.randint(5, 25),
                order_id=random.randint(4000, 9999)
            )
            filler_count += 1

        detected_w = BTC_RE.findall(text)
        detected_k = [kw for kw in DRUG_KEYWORDS if kw in text.lower()]

        messages_to_add.append(TelegramMessage(
            channel_id=ch_obj.id,
            sender_handle=sender,
            message_text=text,
            detected_wallets_json=json.dumps(detected_w),
            detected_keywords_json=json.dumps(detected_k),
            timestamp=msg_timestamp
        ))

    db.bulk_save_objects(messages_to_add)
    db.commit()

    prov = DataProvenance(
        source_type="Telegram Channel Export",
        source_name="Enriched Synthetic Telegram Message Stream",
        source_identifier="telegram/enriched_synthetic_generator",
        collection_method="Non-persuasive procedural keyword & wallet regex validation pipeline with real DB cross-referencing",
        collected_at=utc_now(),
        integrity_hash="SHA256:TELEGRAM_ENRICHED_SYNTHETIC_V2"
    )
    db.add(prov)
    db.commit()

    summary_info = {
        "channel_count": len(channels_data),
        "message_count": len(messages_to_add),
        "linked_message_count": linked_count,
        "filler_message_count": filler_count,
        "merged_handles": merged_handles,
        "standalone_handles": standalone_handles,
        "sample_messages": [m.message_text for m in messages_to_add[:8]]
    }

    print(f"[ingest_telegram] Ingested {len(channels_data)} Telegram channels and {len(messages_to_add)} messages ({linked_count} cross-referenced linked, {filler_count} generic filler).")
    return (len(channels_data), len(messages_to_add), summary_info)

def run_ingestion(db: Session = None):
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        ch_cnt, msg_cnt, info = ingest_synthetic_telegram(db)
        print(f"[ingest_telegram] Completed Telegram ingestion successfully.")
    finally:
        if close_session:
            db.close()

if __name__ == "__main__":
    run_ingestion()

