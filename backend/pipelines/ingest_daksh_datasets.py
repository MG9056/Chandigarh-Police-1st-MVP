"""
Pipeline: Ingest network-flow datasets (DATASETS/*.csv) into network_traffic_flows.

Schema-based, same philosophy as backend/real_data/loader.py: nothing here
is keyed off an exact filename. Point NETWORK_DATASETS_ROOT (or the default
DATASETS/ folder at the repo root) at any mix of network-flow CSVs — CIC
-Darknet2020-style exports, Daksh's Binary/MultiTotal captures, differently
-cased or renamed files, any subset, mixed in one folder or split across
several — and each file is classified by inspecting its actual columns
(falling back to sampling real values when column names alone are
ambiguous), never by matching a fixed name.

A file whose schema doesn't look like a network flow export is skipped with
a logged reason; it never takes down ingestion of the rest of the directory.

Override the scan root via env var if your data lives somewhere else:
NETWORK_DATASETS_ROOT
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy.orm import Session

from database import SessionLocal
from models import NetworkTrafficFlow, DataProvenance, utc_now

_HERE = os.path.dirname(os.path.abspath(__file__))

DATASETS_DIR = os.environ.get(
    "NETWORK_DATASETS_ROOT",
    os.path.abspath(os.path.join(_HERE, "..", "..", "DATASETS")),
)

# --- Column alias groups -----------------------------------------------------
# Every known export names these differently ("Flow ID" vs "flow_id" vs
# "flowid"); we normalize (lower, strip, spaces->underscores) and match
# against alias sets rather than hardcoding one dataset's convention.
_FLOW_ID_ALIASES = {"flow_id", "flowid", "id"}
_SRC_IP_ALIASES = {"src_ip", "source_ip", "srcip", "sourceip"}
_DST_IP_ALIASES = {"dst_ip", "dest_ip", "destination_ip", "dstip", "destip"}
_SRC_PORT_ALIASES = {"src_port", "source_port", "srcport", "sourceport"}
_DST_PORT_ALIASES = {"dst_port", "dest_port", "destination_port", "dstport", "destport"}
_PROTOCOL_ALIASES = {"protocol", "proto"}
_TIMESTAMP_ALIASES = {"timestamp", "time", "date", "datetime", "flow_start_time"}

# Values seen across different label vocabularies that indicate anonymizing /
# encrypted transport. Checked against *any* label-like column's value —
# this is what lets one heuristic work across Darknet.CSV's "Tor"/"VPN",
# Binary's "Encrypted", and MultiTotal's "TOR"/"ZERONET"/"I2P"/etc. without
# per-file special-casing.
_ENCRYPTED_KEYWORDS = {"tor", "vpn", "i2p", "zeronet", "freenet", "encrypted", "onion"}

IPV4_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def _log(msg: str) -> None:
    print(f"[ingest_daksh] {msg}")


def _normalize(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace(".", "_")


def _find_col(colmap: dict[str, str], aliases: set[str]) -> str | None:
    for norm, original in colmap.items():
        if norm in aliases:
            return original
    return None


def _looks_like_ipv4(series: pd.Series, sample_size: int = 50) -> bool:
    sample = series.dropna().astype(str).head(sample_size)
    if len(sample) == 0:
        return False
    return sample.apply(lambda v: bool(IPV4_RE.match(v))).mean() >= 0.6


@dataclass
class FlowSchema:
    """Resolved column mapping for one recognized network-flow file."""
    path: str
    flow_id_col: str | None
    src_ip_col: str
    dst_ip_col: str
    src_port_col: str | None
    dst_port_col: str | None
    protocol_col: str | None
    timestamp_col: str | None
    label_cols: list[str] = field(default_factory=list)  # any/all "label*" columns, in file order


def classify_network_flow_csv(path: str) -> FlowSchema | None:
    """
    Inspects a CSV's columns (and, if named src/dst IP columns aren't found,
    samples real values) to decide whether it's a network-flow export and,
    if so, how its columns map onto our schema. Returns None for anything
    unrecognized — never raises, so one stray file can't break the batch.
    """
    try:
        header_df = pd.read_csv(path, nrows=0)
    except Exception as e:
        _log(f"{os.path.basename(path)}: couldn't read header ({e}) — skipping.")
        return None

    cols = list(header_df.columns)
    if not cols:
        return None

    colmap = {_normalize(c): c for c in cols}

    src_ip_col = _find_col(colmap, _SRC_IP_ALIASES)
    dst_ip_col = _find_col(colmap, _DST_IP_ALIASES)

    # Names alone didn't resolve it — sample real values and look for the
    # two most IP-shaped columns, same fallback spirit as loader.py's
    # content-based edge-list classification.
    if src_ip_col is None or dst_ip_col is None:
        try:
            sample = pd.read_csv(path, nrows=200)
        except Exception as e:
            _log(f"{os.path.basename(path)}: couldn't sample content ({e}) — skipping.")
            return None
        ip_like_cols = [c for c in cols if sample[c].dtype == object and _looks_like_ipv4(sample[c])]
        if len(ip_like_cols) >= 2:
            src_ip_col, dst_ip_col = ip_like_cols[0], ip_like_cols[1]
        else:
            _log(f"{os.path.basename(path)}: no recognizable src/dst IP columns — skipping (unrecognized schema).")
            return None

    label_cols = [c for c in cols if "label" in _normalize(c)]

    return FlowSchema(
        path=path,
        flow_id_col=_find_col(colmap, _FLOW_ID_ALIASES),
        src_ip_col=src_ip_col,
        dst_ip_col=dst_ip_col,
        src_port_col=_find_col(colmap, _SRC_PORT_ALIASES),
        dst_port_col=_find_col(colmap, _DST_PORT_ALIASES),
        protocol_col=_find_col(colmap, _PROTOCOL_ALIASES),
        timestamp_col=_find_col(colmap, _TIMESTAMP_ALIASES),
        label_cols=label_cols,
    )


def _nullable_int_column(series: pd.Series) -> list:
    """Vectorized int-or-None conversion — avoids a Python-level int()/try
    per row (the dominant cost of the old iterrows loop)."""
    numeric = pd.to_numeric(series, errors="coerce")
    # .tolist() on a float64 series with NaNs, then a single fast pass to
    # swap NaN -> None and float -> int, is far cheaper than doing the
    # same per-row inside a pandas Series (iterrows) context.
    return [None if v != v else int(v) for v in numeric.tolist()]  # v != v is the fast NaN check


def _vectorized_is_encrypted(df: pd.DataFrame, label_cols: list[str]) -> pd.Series:
    """OR together the encrypted-keyword match across every label-like
    column, all as vectorized pandas string ops — no per-row Python calls."""
    if not label_cols:
        return pd.Series(False, index=df.index)
    result = pd.Series(False, index=df.index)
    for col in label_cols:
        normalized = df[col].astype(str).str.strip().str.lower()
        result = result | normalized.isin(_ENCRYPTED_KEYWORDS)
    return result


def _build_flow_records(df: pd.DataFrame, schema: FlowSchema, source_dataset: str) -> list[dict]:
    """Transforms a raw chunk into NetworkTrafficFlow-shaped dicts using
    vectorized pandas column operations end-to-end (no iterrows)."""
    primary_label_col = schema.label_cols[0] if schema.label_cols else None
    secondary_label_col = schema.label_cols[1] if len(schema.label_cols) > 1 else None

    out = pd.DataFrame(index=df.index)
    out["flow_id"] = df[schema.flow_id_col].astype(str) if schema.flow_id_col else ""
    out["src_ip"] = df[schema.src_ip_col].astype(str)
    out["dst_ip"] = df[schema.dst_ip_col].astype(str)
    out["src_port"] = _nullable_int_column(df[schema.src_port_col]) if schema.src_port_col else None
    out["dst_port"] = _nullable_int_column(df[schema.dst_port_col]) if schema.dst_port_col else None
    out["protocol"] = df[schema.protocol_col].astype(str) if schema.protocol_col else None
    out["timestamp_str"] = df[schema.timestamp_col].astype(str) if schema.timestamp_col else None
    out["encapsulation_label"] = df[primary_label_col].astype(str) if primary_label_col else None
    out["application_label"] = df[secondary_label_col].astype(str) if secondary_label_col else None
    out["is_encrypted"] = _vectorized_is_encrypted(df, schema.label_cols)
    out["source_dataset"] = source_dataset

    return out.to_dict("records")


def ingest_network_flow_csv(
    db: Session,
    schema: FlowSchema,
    sample_limit: int = 5000,
    chunk_size: int = 200_000,
) -> int:
    """
    Ingests one already-classified network-flow CSV using its resolved
    column map. Streams the file in chunks (pandas' own chunked C parser)
    and builds/writes each chunk with vectorized pandas ops + bulk_insert_
    mappings, rather than materializing every row as a Python ORM object
    (bulk_save_objects) via a row-by-row iterrows() loop. That combination
    is what makes raising sample_limit toward the millions actually
    tractable instead of taking hours: iterrows() alone made a plain
    200k-row file take ~8s just to walk, before the DB write; ORM object
    construction (bulk_save_objects) roughly doubled that again.
    """
    source_dataset = os.path.basename(schema.path)
    total_rows = 0

    reader = pd.read_csv(
        schema.path,
        nrows=sample_limit,
        low_memory=False,
        on_bad_lines="skip",
        chunksize=chunk_size,
    )
    for chunk_num, chunk in enumerate(reader, start=1):
        chunk.columns = [c.strip() for c in chunk.columns]
        records = _build_flow_records(chunk, schema, source_dataset)
        db.bulk_insert_mappings(NetworkTrafficFlow, records)
        db.commit()
        total_rows += len(records)
        _log(f"  {source_dataset}: chunk {chunk_num} — {total_rows:,} rows written so far...")

    provenance = DataProvenance(
        source_type="Network Traffic Dataset",
        source_name=source_dataset,
        source_identifier=os.path.relpath(schema.path, DATASETS_DIR),
        collection_method="Schema-based automated network flow ingestion",
        collected_at=utc_now(),
        integrity_hash=f"SHA256:AUTO_{source_dataset.upper()}",
    )
    db.add(provenance)
    db.commit()

    _log(f"Successfully ingested {total_rows:,} rows from {source_dataset}")
    return total_rows


def _scan_datasets_dir(root: str) -> list[str]:
    """Case-insensitive recursive CSV discovery — glob's *.csv pattern is
    case-sensitive on Linux and silently misses files like 'Darknet.CSV'."""
    if not os.path.isdir(root):
        return []
    found = []
    for dirpath, _dirs, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".csv"):
                found.append(os.path.join(dirpath, name))
    return found


def run_ingestion(db: Session = None, sample_limit: int = 5000, chunk_size: int = 200_000):
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        if not os.path.isdir(DATASETS_DIR):
            _log(f"Skipping — {DATASETS_DIR} not found (set NETWORK_DATASETS_ROOT to override).")
            return 0

        candidates = _scan_datasets_dir(DATASETS_DIR)
        _log(f"Scanning {len(candidates)} CSV file(s) under {DATASETS_DIR}...")

        total = 0
        for path in candidates:
            schema = classify_network_flow_csv(path)
            if schema is None:
                continue
            total += ingest_network_flow_csv(db, schema, sample_limit=sample_limit, chunk_size=chunk_size)

        _log(f"Total Network Traffic Flow rows ingested: {total}")
        return total
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    run_ingestion()