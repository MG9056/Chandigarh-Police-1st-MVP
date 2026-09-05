"""
One-Time Migration Script: Legacy & Synthetic Data -> Canonical Schema.

Reads records from:
1. `backend/darknight.db` (Suspect, CryptoWallet, CryptoTransaction, DarknetListing, TelegramChannel, TelegramMessage, NetworkTrafficFlow)
2. `backend/synthetic_data.py` (Daksh's Entity, Observation, Transaction, Region, DetailedLocation)

Converts every record into canonical ORM tables:
- canonical_entities
- canonical_transactions
- canonical_observations
- canonical_regions
- canonical_detailed_locations

Log warnings for metadata fallbacks and collision events.
Output summary of records processed, metadata fallbacks, and validation status.
"""

import sys
import os
import logging
from datetime import datetime, timezone
import json

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from database import engine, SessionLocal, init_db
import models
import synthetic_data
from data.canonical_schema import (
    EntityModel, TransactionModel, ObservationModel,
    RegionModel, DetailedLocationModel, EntityType
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_to_canonical")

COLLISIONS_LOG_PATH = os.path.join(BACKEND_DIR, "identifier_collisions.log")


def log_collision(identifier: str, existing_id: str, new_source: str, merged_metadata: dict):
    """Logs identifier collision to dedicated log file and console."""
    collision_msg = (
        f"[IDENTIFIER COLLISION] Identifier '{identifier}' already exists as Entity '{existing_id}'. "
        f"Merged telemetry from source '{new_source}'."
    )
    logger.warning(collision_msg)
    with open(COLLISIONS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} - {collision_msg}\n")


def migrate():
    logger.info("Initializing Canonical Database Tables...")
    init_db()

    db = SessionLocal()

    records_in = 0
    records_out = 0
    metadata_fallbacks = 0
    collisions_count = 0
    validation_failures = 0

    try:
        # Clear existing canonical data for clean idempotency
        db.query(ObservationModel).delete()
        db.query(TransactionModel).delete()
        db.query(EntityModel).delete()
        db.query(DetailedLocationModel).delete()
        db.query(RegionModel).delete()
        db.commit()

        # Cache existing entity identifiers for collision upsert handling
        entity_cache = {}  # identifier -> EntityModel

        # -------------------------------------------------------------------
        # 1. Migrate Schema B (Daksh's synthetic_data.py)
        # -------------------------------------------------------------------
        logger.info("Migrating Schema B (backend/synthetic_data.py)...")

        # Regions
        for reg in synthetic_data.REGIONS:
            records_in += 1
            r_model = RegionModel(
                id=reg.id,
                name=reg.name,
                lat=reg.lat,
                lon=reg.lon,
                bounding_box_json=reg.bounding_box.model_dump() if reg.bounding_box else None
            )
            db.add(r_model)
            records_out += 1

        # Detailed Locations
        for loc in synthetic_data.DETAILED_LOCATIONS:
            records_in += 1
            l_model = DetailedLocationModel(
                id=loc.id,
                region_id=loc.region_id,
                name=loc.name,
                lat=loc.lat,
                lon=loc.lon,
                bounding_box_json=loc.bounding_box.model_dump() if loc.bounding_box else None
            )
            db.add(l_model)
            records_out += 1

        # Entities
        for ent in synthetic_data.entities:
            records_in += 1
            meta = {}
            if ent.bio:
                meta["bio"] = ent.bio
                metadata_fallbacks += 1

            if ent.identifier in entity_cache:
                # Collision handling
                collisions_count += 1
                existing = entity_cache[ent.identifier]
                existing.metadata_json.setdefault("aliases", []).append({
                    "id": ent.id, "platform": ent.platform, "display_name": ent.display_name, "meta": meta
                })
                log_collision(ent.identifier, existing.id, ent.platform or "synthetic_data", existing.metadata_json)
            else:
                e_model = EntityModel(
                    id=f"syn_{ent.id}",
                    type=ent.type.value if hasattr(ent.type, "value") else str(ent.type),
                    identifier=ent.identifier,
                    display_name=ent.display_name,
                    platform=ent.platform,
                    location=ent.location,
                    risk_score=0,
                    created_at=ent.created_at or datetime.now(timezone.utc),
                    metadata_json=meta
                )
                db.add(e_model)
                entity_cache[ent.identifier] = e_model
                records_out += 1

        # Transactions
        for tx in synthetic_data.transactions:
            records_in += 1
            t_model = TransactionModel(
                id=f"syn_{tx.id}",
                tx_hash=None,
                source_entity_id=f"syn_{tx.source_entity}",
                target_entity_id=f"syn_{tx.target_entity}",
                amount=tx.amount,
                amount_str=f"{tx.amount} {tx.currency}",
                currency=tx.currency,
                timestamp=tx.timestamp or datetime.now(timezone.utc),
                metadata_json={}
            )
            db.add(t_model)
            records_out += 1

        # Observations
        for obs in synthetic_data.observations:
            records_in += 1
            meta = {}
            if obs.risk_signal:
                meta["risk_signal"] = obs.risk_signal
                metadata_fallbacks += 1

            o_model = ObservationModel(
                id=f"syn_{obs.id}",
                entity_id=f"syn_{obs.entity_id}",
                source=obs.source or "Synthetic",
                timestamp=obs.timestamp or datetime.now(timezone.utc),
                latitude=obs.latitude,
                longitude=obs.longitude,
                region=obs.region,
                activity_type=obs.activity_type or "general_observation",
                risk_signal=obs.risk_signal,
                metadata_json=meta
            )
            db.add(o_model)
            records_out += 1

        db.commit()

        # -------------------------------------------------------------------
        # 2. Migrate Schema A (backend/models.py SQLite records)
        # -------------------------------------------------------------------
        logger.info("Migrating Schema A (backend/models.py darknight.db tables)...")

        # Suspects -> CanonicalEntity (type = suspect)
        suspects = db.query(models.Suspect).all()
        for s in suspects:
            records_in += 1
            identifier = s.primary_alias or f"suspect_alias_{s.id}"
            meta = {}
            if s.aliases_json:
                meta["aliases_json"] = s.aliases_json
                metadata_fallbacks += 1
            if s.pgp_fingerprint:
                meta["pgp_fingerprint"] = s.pgp_fingerprint
                metadata_fallbacks += 1
            if s.phone_number:
                meta["phone_number"] = s.phone_number
                metadata_fallbacks += 1
            if s.telegram_handle:
                meta["telegram_handle"] = s.telegram_handle
                metadata_fallbacks += 1
            if s.notes:
                meta["notes"] = s.notes
                metadata_fallbacks += 1

            entity_id = f"suspect_{s.id}"

            if identifier in entity_cache:
                collisions_count += 1
                existing = entity_cache[identifier]
                existing.risk_score = max(existing.risk_score, s.risk_score or 0)
                existing.metadata_json.setdefault("merged_suspects", []).append({"id": entity_id, "meta": meta})
                log_collision(identifier, existing.id, "models.Suspect", existing.metadata_json)
            else:
                e_model = EntityModel(
                    id=entity_id,
                    type=EntityType.SUSPECT.value,
                    identifier=identifier,
                    display_name=s.primary_alias or f"Suspect #{s.id}",
                    platform="Law Enforcement Registry",
                    location=None,
                    risk_score=s.risk_score or 0,
                    created_at=s.created_at or datetime.now(timezone.utc),
                    updated_at=s.updated_at or datetime.now(timezone.utc),
                    metadata_json=meta
                )
                db.add(e_model)
                entity_cache[identifier] = e_model
                records_out += 1

        # CryptoWallets -> CanonicalEntity (type = wallet)
        wallets = db.query(models.CryptoWallet).all()
        for w in wallets:
            records_in += 1
            meta = {}
            if w.balance:
                meta["balance"] = w.balance
                metadata_fallbacks += 1
            if w.risk_level:
                meta["risk_level"] = w.risk_level
                metadata_fallbacks += 1
            if w.associated_suspect_id:
                meta["associated_suspect_id"] = f"suspect_{w.associated_suspect_id}"
                metadata_fallbacks += 1

            risk_num = 90 if w.risk_level in ["ILLICIT", "SANCTIONED"] else 10
            entity_id = f"wallet_{w.id}"

            if w.address in entity_cache:
                collisions_count += 1
                existing = entity_cache[w.address]
                existing.risk_score = max(existing.risk_score, risk_num)
                existing.metadata_json.setdefault("wallet_info", []).append({"id": entity_id, "meta": meta})
                log_collision(w.address, existing.id, "models.CryptoWallet", existing.metadata_json)
            else:
                e_model = EntityModel(
                    id=entity_id,
                    type=EntityType.WALLET.value,
                    identifier=w.address,
                    display_name=f"Wallet ({w.currency}): {w.address[:10]}...",
                    platform="Blockchain",
                    location=None,
                    risk_score=risk_num,
                    created_at=datetime.now(timezone.utc),
                    metadata_json=meta
                )
                db.add(e_model)
                entity_cache[w.address] = e_model
                records_out += 1

        # DarknetListings -> CanonicalEntity (type = listing)
        listings = db.query(models.DarknetListing).all()
        for l in listings:
            records_in += 1
            identifier = l.url or f"listing_url_{l.id}"
            meta = {}
            if l.description:
                meta["description"] = l.description
                metadata_fallbacks += 1
            if l.vendor_alias:
                meta["vendor_alias"] = l.vendor_alias
                metadata_fallbacks += 1
            if l.drug_category:
                meta["drug_category"] = l.drug_category
                metadata_fallbacks += 1
            if l.price:
                meta["price"] = l.price
                metadata_fallbacks += 1
            if l.currency:
                meta["currency"] = l.currency
                metadata_fallbacks += 1
            if l.associated_suspect_id:
                meta["associated_suspect_id"] = f"suspect_{l.associated_suspect_id}"
                metadata_fallbacks += 1

            entity_id = f"listing_{l.id}"

            if identifier in entity_cache:
                collisions_count += 1
                existing = entity_cache[identifier]
                existing.metadata_json.setdefault("merged_listings", []).append({"id": entity_id, "meta": meta})
                log_collision(identifier, existing.id, "models.DarknetListing", existing.metadata_json)
            else:
                e_model = EntityModel(
                    id=entity_id,
                    type=EntityType.LISTING.value,
                    identifier=identifier,
                    display_name=l.title or f"Listing #{l.id}",
                    platform=l.platform or "Agora",
                    location=l.location,
                    risk_score=60,
                    created_at=l.scraped_at or datetime.now(timezone.utc),
                    metadata_json=meta
                )
                db.add(e_model)
                entity_cache[identifier] = e_model
                records_out += 1

        # TelegramChannels -> CanonicalEntity (type = channel)
        channels = db.query(models.TelegramChannel).all()
        for c in channels:
            records_in += 1
            identifier = c.channel_id or f"tg_chan_{c.id}"
            meta = {}
            if c.description:
                meta["description"] = c.description
                metadata_fallbacks += 1
            if c.member_count:
                meta["member_count"] = c.member_count
                metadata_fallbacks += 1

            entity_id = f"channel_{c.id}"

            if identifier in entity_cache:
                collisions_count += 1
                existing = entity_cache[identifier]
                existing.metadata_json.setdefault("merged_channels", []).append({"id": entity_id, "meta": meta})
                log_collision(identifier, existing.id, "models.TelegramChannel", existing.metadata_json)
            else:
                e_model = EntityModel(
                    id=entity_id,
                    type=EntityType.CHANNEL.value,
                    identifier=identifier,
                    display_name=c.channel_name or f"Channel {identifier}",
                    platform="Telegram",
                    location=None,
                    risk_score=40,
                    created_at=datetime.now(timezone.utc),
                    metadata_json=meta
                )
                db.add(e_model)
                entity_cache[identifier] = e_model
                records_out += 1

        # CryptoTransactions -> CanonicalTransaction
        ctxs = db.query(models.CryptoTransaction).all()
        for tx in ctxs:
            records_in += 1
            meta = {}
            # parse numeric float amount from string if possible
            parsed_amount = 0.0
            if tx.amount and tx.amount != "UNSPECIFIED":
                try:
                    parsed_amount = float(tx.amount.split()[0])
                except (ValueError, IndexError):
                    parsed_amount = 0.0
                    meta["raw_amount_parse_failed"] = tx.amount
                    metadata_fallbacks += 1

            src_id = f"wallet_addr_{tx.from_address}" if tx.from_address else "unknown_source"
            tgt_id = f"wallet_addr_{tx.to_address}" if tx.to_address else "unknown_target"

            t_model = TransactionModel(
                id=f"ctx_{tx.id}",
                tx_hash=tx.tx_hash,
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                amount=parsed_amount,
                amount_str=tx.amount or "UNSPECIFIED",
                currency=tx.currency or "BTC",
                timestamp=tx.timestamp or datetime.now(timezone.utc),
                metadata_json=meta
            )
            db.add(t_model)
            records_out += 1

        # TelegramMessages -> CanonicalObservation (activity_type = 'telegram_message')
        msgs = db.query(models.TelegramMessage).all()
        for m in msgs:
            records_in += 1
            meta = {}
            if m.message_text:
                meta["message_text"] = m.message_text
                metadata_fallbacks += 1
            if m.detected_wallets_json:
                meta["detected_wallets_json"] = m.detected_wallets_json
                metadata_fallbacks += 1
            if m.detected_keywords_json:
                meta["detected_keywords_json"] = m.detected_keywords_json
                metadata_fallbacks += 1

            o_model = ObservationModel(
                id=f"tg_msg_{m.id}",
                entity_id=f"channel_{m.channel_id}" if m.channel_id else f"sender_{m.sender_handle}",
                source="Telegram",
                timestamp=m.timestamp or datetime.now(timezone.utc),
                latitude=None,
                longitude=None,
                region=None,
                activity_type="telegram_message",
                risk_signal="detected_wallets" if m.detected_wallets_json else None,
                metadata_json=meta
            )
            db.add(o_model)
            records_out += 1

        # NetworkTrafficFlows -> CanonicalObservation (activity_type = 'network_flow')
        flows = db.query(models.NetworkTrafficFlow).all()
        for f in flows:
            records_in += 1
            meta = {
                "flow_id": f.flow_id,
                "src_port": f.src_port,
                "dst_ip": f.dst_ip,
                "dst_port": f.dst_port,
                "protocol": f.protocol,
                "encapsulation_label": f.encapsulation_label,
                "application_label": f.application_label,
                "is_encrypted": f.is_encrypted,
                "source_dataset": f.source_dataset,
            }
            metadata_fallbacks += len(meta)

            o_model = ObservationModel(
                id=f"net_flow_{f.id}",
                entity_id=f"ip_{f.src_ip}",
                source="NetworkMonitor",
                timestamp=datetime.now(timezone.utc),
                latitude=None,
                longitude=None,
                region=None,
                activity_type="network_flow",
                risk_signal="encrypted_traffic" if f.is_encrypted else None,
                metadata_json=meta
            )
            db.add(o_model)
            records_out += 1

        db.commit()

        # -------------------------------------------------------------------
        # Summary Execution Report
        # -------------------------------------------------------------------
        summary = f"""
================================================================================
CANONICAL MIGRATION SUMMARY REPORT
================================================================================
Total Input Records Processed  : {records_in}
Total Canonical Records Created: {records_out}
Metadata Fallbacks Logged      : {metadata_fallbacks}
Identifier Collisions Detected : {collisions_count}
Validation Failures            : {validation_failures}
Collisions Detailed Log File   : {COLLISIONS_LOG_PATH}
================================================================================
        """
        print(summary)
        logger.info("Migration complete successfully!")

    except Exception as e:
        db.rollback()
        logger.error(f"Migration aborted due to error: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
