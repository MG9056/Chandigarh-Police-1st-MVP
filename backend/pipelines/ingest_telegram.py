"""
Pipeline: Ingest Telegram Channels & Synthetic Messages using non-persuasive test templates.
Links each distinct sender_handle to a Suspect record via telegram_handle.
"""

from __future__ import annotations

import json
import re
import random
from sqlalchemy.orm import Session
from database import SessionLocal
from models import TelegramChannel, TelegramMessage, Suspect, DataProvenance, utc_now
from real_data.config import BTC_ADDRESS_REGEX

BTC_RE = re.compile(BTC_ADDRESS_REGEX)

DRUG_KEYWORDS = [
    "opioids", "cannabis", "stimulants", "heroine_sample", "synthetic_drugs",
    "fentanyl_test", "tramadol_ref", "mdma_specimen", "prescription_meds"
]

def ingest_synthetic_telegram(db: Session) -> tuple[int, int]:
    print("[ingest_telegram] Generating Telegram channels & non-persuasive test messages...")

    channels_data = [
        {"channel_id": "ch_1001", "channel_name": "@ChandigarhPharmaNet", "description": "Automated log reference channel #1", "member_count": 1420},
        {"channel_id": "ch_1002", "channel_name": "@DarkTriadDiscussions", "description": "Automated log reference channel #2", "member_count": 890},
        {"channel_id": "ch_1003", "channel_name": "@EncryptedSupplyNorth", "description": "Automated log reference channel #3", "member_count": 2150},
        {"channel_id": "ch_1004", "channel_name": "@PharmaTestChannel", "description": "Automated log reference channel #4", "member_count": 640},
        {"channel_id": "ch_1005", "channel_name": "@CryptoDrugDesk", "description": "Automated log reference channel #5", "member_count": 3100},
    ]

    channels_map = {}
    for c_info in channels_data:
        ch = db.query(TelegramChannel).filter(TelegramChannel.channel_id == c_info["channel_id"]).first()
        if not ch:
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

    # Test Bitcoin Wallet Addresses to embed in messages for regex parsing validation
    test_wallets = [
        "123WBUDmSJv4GctdVEz6Qq6z8nXSKrJ4KX",
        "125W5ek3DT6Zqy5S2iPt4FHQdNMCbZA3FU",
        "1295rkVyNfFpqZpXvKGhDqwhP1jZcNNDMV",
        "13RH4JaFhaCxDGPyYE9emjp2aDxdX18uBA",
        "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    ]

    test_handles = ["@AlphaNode_CDG", "@PharmaTech_99", "@LogInspector", "@TriadRelay", "@NordicVendor", "@DeltaAgent"]

    # Ensure a Suspect record exists for each distinct sender_handle
    for handle in test_handles:
        clean_h = handle.lstrip("@")
        suspect = db.query(Suspect).filter((Suspect.telegram_handle == handle) | (Suspect.primary_alias == clean_h)).first()
        if not suspect:
            suspect = Suspect(
                primary_alias=clean_h,
                aliases_json=json.dumps([clean_h, handle]),
                telegram_handle=handle,
                notes=f"Telegram channel active sender handle: {handle}",
                risk_score=70
            )
            db.add(suspect)
            db.commit()

    messages_to_add = []
    random.seed(42)

    for i in range(1, 51):
        ch_id = f"ch_100{((i - 1) % 5) + 1}"
        ch_obj = channels_map[ch_id]
        sender = random.choice(test_handles)
        kw = random.choice(DRUG_KEYWORDS)
        w_addr = random.choice(test_wallets)

        text = f"Test message log entry #{i:03d} flagging parameter keyword '{kw}' and reference wallet address {w_addr} for detection verification."

        detected_w = BTC_RE.findall(text)
        detected_k = [kw] if kw in text else []

        messages_to_add.append(TelegramMessage(
            channel_id=ch_obj.id,
            sender_handle=sender,
            message_text=text,
            detected_wallets_json=json.dumps(detected_w),
            detected_keywords_json=json.dumps(detected_k),
            timestamp=utc_now()
        ))

    db.bulk_save_objects(messages_to_add)
    db.commit()

    prov = DataProvenance(
        source_type="Telegram Channel Export",
        source_name="Synthetic Telegram Test Message Stream",
        source_identifier="telegram/synthetic_test_generator",
        collection_method="Non-persuasive automated keyword & wallet regex validation pipeline",
        collected_at=utc_now(),
        integrity_hash="SHA256:TELEGRAM_SYNTHETIC_TEST"
    )
    db.add(prov)
    db.commit()

    print(f"[ingest_telegram] Ingested {len(channels_data)} Telegram channels and {len(messages_to_add)} synthetic test messages.")
    return (len(channels_data), len(messages_to_add))

def run_ingestion(db: Session = None):
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        ch_cnt, msg_cnt = ingest_synthetic_telegram(db)
        print(f"[ingest_telegram] Completed Telegram ingestion. Channels: {ch_cnt}, Messages: {msg_cnt}")
    finally:
        if close_session:
            db.close()

if __name__ == "__main__":
    run_ingestion()
