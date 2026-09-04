"""
Pipeline: Ingest Daksh's Dataset Collection (DATASETS/*.csv) into network_traffic_flows.
"""

from __future__ import annotations

import os
import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal
from models import NetworkTrafficFlow, DataProvenance, utc_now

DATASETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "DATASETS"))

def ingest_darknet_csv(db: Session, sample_limit: int = 5000) -> int:
    path = os.path.join(DATASETS_DIR, "Darknet.CSV")
    if not os.path.exists(path):
        print(f"[ingest_daksh] Skipping {path} (file not found)")
        return 0

    print(f"[ingest_daksh] Reading {path} (limit={sample_limit})...")
    df = pd.read_csv(path, nrows=sample_limit, low_memory=False, on_bad_lines='skip')
    df.columns = [c.strip() for c in df.columns]

    flows = []
    for _, row in df.iterrows():
        flow_id = str(row.get("Flow ID", ""))
        src_ip = str(row.get("Src IP", ""))
        dst_ip = str(row.get("Dst IP", ""))
        try:
            src_port = int(row.get("Src Port", 0))
        except (ValueError, TypeError):
            src_port = None
        try:
            dst_port = int(row.get("Dst Port", 0))
        except (ValueError, TypeError):
            dst_port = None

        protocol = str(row.get("Protocol", ""))
        timestamp_str = str(row.get("Timestamp", ""))
        encap_label = str(row.get("Label", ""))
        app_label = str(row.get("Label.1", ""))

        is_enc = encap_label.lower() in ["tor", "vpn"]

        flows.append(NetworkTrafficFlow(
            flow_id=flow_id,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
            protocol=protocol,
            timestamp_str=timestamp_str,
            encapsulation_label=encap_label,
            application_label=app_label,
            is_encrypted=is_enc,
            source_dataset="Darknet.CSV"
        ))

    db.bulk_save_objects(flows)

    provenance = DataProvenance(
        source_type="Network Traffic Dataset",
        source_name="Darknet.CSV (CIC-Darknet2020)",
        source_identifier="DATASETS/Darknet.CSV",
        collection_method="Authorized academic traffic flow collection",
        collected_at=utc_now(),
        integrity_hash="SHA256:DATASETS_DARKNET_CSV"
    )
    db.add(provenance)
    db.commit()

    print(f"[ingest_daksh] Successfully ingested {len(flows)} rows from Darknet.CSV")
    return len(flows)

def ingest_binary_csv(db: Session, sample_limit: int = 5000) -> int:
    path = os.path.join(DATASETS_DIR, "Binary -2DSCombined.csv")
    if not os.path.exists(path):
        print(f"[ingest_daksh] Skipping {path} (file not found)")
        return 0

    print(f"[ingest_daksh] Reading {path} (limit={sample_limit})...")
    df = pd.read_csv(path, nrows=sample_limit, low_memory=False, on_bad_lines='skip')
    df.columns = [c.strip() for c in df.columns]

    flows = []
    for _, row in df.iterrows():
        flow_id = str(row.get("flow_id", ""))
        src_ip = str(row.get("src_ip", ""))
        dst_ip = str(row.get("dst_ip", ""))
        try:
            src_port = int(row.get("src_port", 0))
        except (ValueError, TypeError):
            src_port = None
        try:
            dst_port = int(row.get("dst_port", 0))
        except (ValueError, TypeError):
            dst_port = None

        protocol = str(row.get("protocol", ""))
        timestamp_str = str(row.get("timestamp", ""))
        lbl = str(row.get("label", ""))

        is_enc = (lbl.lower() == "encrypted")

        flows.append(NetworkTrafficFlow(
            flow_id=flow_id,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
            protocol=protocol,
            timestamp_str=timestamp_str,
            encapsulation_label=lbl,
            application_label=None,
            is_encrypted=is_enc,
            source_dataset="Binary -2DSCombined.csv"
        ))

    db.bulk_save_objects(flows)

    provenance = DataProvenance(
        source_type="Network Traffic Dataset",
        source_name="Binary -2DSCombined.csv",
        source_identifier="DATASETS/Binary -2DSCombined.csv",
        collection_method="Statistical flow feature entropy extraction",
        collected_at=utc_now(),
        integrity_hash="SHA256:DATASETS_BINARY_CSV"
    )
    db.add(provenance)
    db.commit()

    print(f"[ingest_daksh] Successfully ingested {len(flows)} rows from Binary -2DSCombined.csv")
    return len(flows)

def ingest_multitotal_csv(db: Session, sample_limit: int = 5000) -> int:
    path = os.path.join(DATASETS_DIR, "MultiTotalDS.csv")
    if not os.path.exists(path):
        print(f"[ingest_daksh] Skipping {path} (file not found)")
        return 0

    print(f"[ingest_daksh] Reading {path} (limit={sample_limit})...")
    df = pd.read_csv(path, nrows=sample_limit, low_memory=False, on_bad_lines='skip')
    df.columns = [c.strip() for c in df.columns]

    flows = []
    for _, row in df.iterrows():
        flow_id = str(row.get("flow_id", ""))
        src_ip = str(row.get("src_ip", ""))
        dst_ip = str(row.get("dst_ip", ""))
        try:
            src_port = int(row.get("src_port", 0))
        except (ValueError, TypeError):
            src_port = None
        try:
            dst_port = int(row.get("dst_port", 0))
        except (ValueError, TypeError):
            dst_port = None

        protocol = str(row.get("protocol", ""))
        timestamp_str = str(row.get("timestamp", ""))
        lbl = str(row.get("label", ""))

        is_enc = lbl.upper() in ["TOR", "ZERONET", "I2P", "VPN", "FREENET"]

        flows.append(NetworkTrafficFlow(
            flow_id=flow_id,
            src_ip=src_ip,
            src_port=src_port,
            dst_ip=dst_ip,
            dst_port=dst_port,
            protocol=protocol,
            timestamp_str=timestamp_str,
            encapsulation_label=lbl,
            application_label=None,
            is_encrypted=is_enc,
            source_dataset="MultiTotalDS.csv"
        ))

    db.bulk_save_objects(flows)

    provenance = DataProvenance(
        source_type="Network Traffic Dataset",
        source_name="MultiTotalDS.csv",
        source_identifier="DATASETS/MultiTotalDS.csv",
        collection_method="Multi-class encrypted network traffic flow analysis",
        collected_at=utc_now(),
        integrity_hash="SHA256:DATASETS_MULTITOTAL_CSV"
    )
    db.add(provenance)
    db.commit()

    print(f"[ingest_daksh] Successfully ingested {len(flows)} rows from MultiTotalDS.csv")
    return len(flows)

def run_ingestion(db: Session = None):
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        t1 = ingest_darknet_csv(db)
        t2 = ingest_binary_csv(db)
        t3 = ingest_multitotal_csv(db)
        print(f"[ingest_daksh] Total Network Traffic Flow rows ingested: {t1 + t2 + t3}")
    finally:
        if close_session:
            db.close()

if __name__ == "__main__":
    run_ingestion()
