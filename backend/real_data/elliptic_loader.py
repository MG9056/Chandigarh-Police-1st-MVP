"""
Loads the Elliptic++ actor-level data: wallet classifications
(address, class), the address-address edge list, and — new — the full
per-wallet feature vector from wallets_features.csv /
wallets_features_classes_combined.csv, so every node in the rendered
graph carries every real feature Elliptic++ computed for that address,
not just its class label and topological degree.

I don't have your actual wallets_features.csv to check its exact
column names against, so this doesn't hardcode a schema: it detects
the id column heuristically and passes every other column through
as-is, whatever it's called. If a feature file isn't present, the
graph still works fine with just class + topology (features are
additive, not required).

Every function here works directly off real rows from disk. Nothing
in this file invents an edge, a label, or a feature value.
"""

from __future__ import annotations

import glob
import os
import sys
import time

import pandas as pd
import networkx as nx

from . import config


def _log(msg: str) -> None:
    """Prints with an immediate flush and elapsed-time stamp so progress
    is visible in the terminal even under uvicorn's reloader, which can
    buffer stdout. Run this module directly (python -m real_data.elliptic_loader)
    to watch these live rather than waiting on a browser request."""
    print(f"[elliptic_loader +{time.time() - _T0:.1f}s] {msg}", flush=True)


_T0 = time.time()

# Optional — only used if you haven't added these to config.py yet.
# Prefer the combined file (features+class from one export, so it can't
# drift out of sync with a separately-exported wallets_classes.csv).
_DEFAULT_FEATURES_CANDIDATES = [
    "wallets_features_classes_combined.csv",
    "wallets_features.csv",
]
FEATURES_CANDIDATES = getattr(
    config, "ELLIPTIC_WALLET_FEATURES_CANDIDATES", _DEFAULT_FEATURES_CANDIDATES
)

# Columns from wallets_features_classes_combined.csv that duplicate
# what load_wallets()/load_edges() already give us — dropped from the
# per-node "features" dict so we don't ship the same class label twice
# under two different keys.
_ID_LIKE_COLUMNS = {"address", "wallet_address", "wallet", "id", "class", "label"}


def _find_file(directory: str, candidates: list[str], fallback_glob: str) -> str:
    """
    Tries exact filenames in priority order first (so a real production
    file always wins over a same-shaped sample file, and a specific edge
    type is never confused with another edge file that happens to share
    a substring, e.g. AddrAddr vs AddrTx vs TxAddr vs txs_edgelist all
    contain "edge"). Falls back to a fuzzy glob only if none of the
    named candidates exist, so unusual export names still work.
    """
    existing = {f.lower(): f for f in os.listdir(directory)} if os.path.isdir(directory) else {}
    for name in candidates:
        if name.lower() in existing:
            return os.path.join(directory, existing[name.lower()])

    matches = sorted(glob.glob(os.path.join(directory, fallback_glob)))
    if matches:
        return matches[0]

    raise FileNotFoundError(
        f"None of {candidates} (or anything matching {fallback_glob!r}) found in {directory}"
    )


def _find_file_optional(directory: str, candidates: list[str]) -> str | None:
    existing = {f.lower(): f for f in os.listdir(directory)} if os.path.isdir(directory) else {}
    for name in candidates:
        if name.lower() in existing:
            return os.path.join(directory, existing[name.lower()])
    return None


def load_wallets(data_dir: str = config.ELLIPTIC_DATA_DIR) -> pd.DataFrame:
    """Returns DataFrame[address, class] — class is 1/2/3 (illicit/licit/unknown)."""
    candidates = getattr(config, "ELLIPTIC_WALLETS_CANDIDATES", ["wallets_classes.csv", "sample_wallets.csv"])
    fallback_glob = getattr(config, "ELLIPTIC_WALLETS_GLOB", "*wallet*.csv")
    path = _find_file(data_dir, candidates, fallback_glob)
    _log(f"loading wallets from {path} ({os.path.getsize(path) / 1e6:.1f} MB)...")
    df = pd.read_csv(path, usecols=["address", "class"], dtype={"address": str, "class": int})
    df = df.drop_duplicates(subset="address")
    _log(f"loaded {len(df)} wallets.")
    return df


def load_edges(data_dir: str = config.ELLIPTIC_DATA_DIR) -> pd.DataFrame:
    """Returns DataFrame[input_address, output_address]."""
    candidates = getattr(config, "ELLIPTIC_EDGES_CANDIDATES", ["AddrAddr_edgelist.csv", "sample_addr_edges.csv"])
    fallback_glob = getattr(config, "ELLIPTIC_EDGES_GLOB", "*edge*.csv")
    path = _find_file(data_dir, candidates, fallback_glob)
    _log(f"loading edges from {path} ({os.path.getsize(path) / 1e6:.1f} MB)...")
    df = pd.read_csv(
        path, usecols=["input_address", "output_address"],
        dtype={"input_address": str, "output_address": str},
    ).dropna()
    _log(f"loaded {len(df)} edges.")
    return df


def _detect_id_column(columns: list[str]) -> str:
    """
    Elliptic++ community exports aren't perfectly consistent about the
    id column name across files — `address` is standard, but variants
    with `wallet_address`, `wallet`, or an unnamed/renamed first column
    show up in the wild. Picks the first recognizable name, else falls
    back to the literal first column so this doesn't hard-fail on a
    file we haven't seen before — it just treats whatever's first as
    the id.
    """
    lower_map = {c.lower(): c for c in columns}
    for candidate in ("address", "wallet_address", "wallet", "id"):
        if candidate in lower_map:
            return lower_map[candidate]
    return columns[0]


def load_wallet_features(data_dir: str = config.ELLIPTIC_DATA_DIR) -> pd.DataFrame | None:
    """
    Returns a DataFrame indexed by `address` with every feature column
    Elliptic++ computed for that wallet — whatever they're actually
    named, nothing here assumes a specific schema — or None if neither
    wallets_features_classes_combined.csv nor wallets_features.csv is
    present (features are optional; the graph still renders with just
    class + topology if you skip this file).

    NOTE: wallets_features.csv / the combined file can be large
    (hundreds of MB in the full Elliptic++ export) — this does a single
    full read since we need every column, but if memory becomes an
    issue on your machine, pass a pre-filtered copy of the file instead
    of the full export.
    """
    path = _find_file_optional(data_dir, FEATURES_CANDIDATES)
    if path is None:
        _log("no wallet features file found — continuing with class + topology only.")
        return None

    _log(f"loading wallet features from {path} ({os.path.getsize(path) / 1e6:.1f} MB) — this is the slow step for large exports...")
    df = pd.read_csv(path, low_memory=False)
    _log(f"read {len(df)} feature rows, {len(df.columns)} columns. Indexing by address...")
    id_col = _detect_id_column(list(df.columns))
    df = df.rename(columns={id_col: "address"})
    df["address"] = df["address"].astype(str)
    result = df.drop_duplicates(subset="address").set_index("address")
    _log("wallet features indexed.")
    return result


def build_illicit_focused_subgraph(
    max_nodes: int = config.MAX_ELLIPTIC_NODES,
    data_dir: str = config.ELLIPTIC_DATA_DIR,
    include_features: bool = True,
) -> dict:
    """
    Real Elliptic++ data, filtered down to something a browser can render.

    Blockchain address graphs have one dominant giant component (in the
    sample data, ~21k of the ~26k illicit-touching addresses) that's too
    tangled to render meaningfully, plus hundreds of small, naturally
    self-contained components. Rather than thinning the giant component
    into a sparse skeleton (tried it, ended up with 120 nodes and 22
    edges — lost all the actual cluster structure), this takes whole
    small components — real, fully-formed sub-clusters from the data —
    greedily by size until the node budget is used, favoring components
    with a higher illicit fraction when sizes are close.

    When a wallet-features file is present (see load_wallet_features),
    each kept node also carries a "features" dict with every real
    feature column for that address, keyed exactly as they appear in
    the source CSV. Nothing here computes or estimates a feature value —
    it's a straight passthrough of what Elliptic++ already calculated,
    with NaN -> None so the result stays valid JSON.

    Returns {"nodes": [...], "edges": [...]}.
    """
    wallets = load_wallets(data_dir)
    edges = load_edges(data_dir)
    features = load_wallet_features(data_dir) if include_features else None

    class_by_addr = dict(zip(wallets.address, wallets["class"]))
    illicit = set(wallets[wallets["class"] == config.ILLICIT_CLASS].address)
    _log(f"{len(illicit)} illicit-labeled wallets. Filtering edge list...")

    touching = edges[
        edges.input_address.isin(illicit) | edges.output_address.isin(illicit)
    ]
    _log(f"{len(touching)} edges touch an illicit wallet.")
    if touching.empty:
        return {"nodes": [], "edges": []}

    _log("building graph (this can be slow at full Elliptic++ scale — millions of edges in pure-Python networkx)...")
    g = nx.from_pandas_edgelist(
        touching, source="input_address", target="output_address"
    )
    g.remove_edges_from(nx.selfloop_edges(g))
    _log(f"graph built: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges. Finding connected components...")

    def illicit_fraction(component: set) -> float:
        return sum(1 for n in component if class_by_addr.get(n) == config.ILLICIT_CLASS) / len(component)

    components = sorted(
        nx.connected_components(g),
        key=lambda c: (len(c), illicit_fraction(c)),
        reverse=True,
    )
    _log(f"found {len(components)} connected components. Largest: {len(components[0])} nodes.")

    kept_nodes: set = set()
    for comp in components:
        if len(kept_nodes) + len(comp) > max_nodes:
            continue
        kept_nodes |= comp
        if len(kept_nodes) >= max_nodes * 0.9:
            break
    _log(f"selected {len(kept_nodes)} nodes for the rendered subgraph.")

    degree = dict(g.degree(kept_nodes))

    def _feature_dict(addr: str) -> dict | None:
        if features is None or addr not in features.index:
            return None
        row = features.loc[addr]
        out = {}
        for col, val in row.items():
            if col.lower() in _ID_LIKE_COLUMNS:
                continue
            if pd.isna(val):
                out[col] = None
            elif hasattr(val, "item"):  # numpy scalar -> native python
                out[col] = val.item()
            else:
                out[col] = val
        return out

    nodes = []
    for addr in kept_nodes:
        node = {
            "address": addr,
            "class": class_by_addr.get(addr, config.UNKNOWN_CLASS),
            "degree": degree.get(addr, 0),
        }
        feat = _feature_dict(addr)
        if feat:
            node["features"] = feat
        nodes.append(node)

    kept_edges = [
        (u, v) for u, v in g.edges(kept_nodes) if u in kept_nodes and v in kept_nodes
    ]
    _log(f"done. {len(nodes)} nodes, {len(kept_edges)} edges in final subgraph.")

    return {"nodes": nodes, "edges": kept_edges}


if __name__ == "__main__":
    data = build_illicit_focused_subgraph()
    print("nodes:", len(data["nodes"]))
    print("edges:", len(data["edges"]))
    illicit_ct = sum(1 for n in data["nodes"] if n["class"] == config.ILLICIT_CLASS)
    print("illicit-labeled among kept nodes:", illicit_ct)
    with_features = [n for n in data["nodes"] if "features" in n]
    print("nodes with a feature vector attached:", len(with_features))
    if with_features:
        print("example feature keys:", list(with_features[0]["features"].keys()))
        print("example node:", with_features[0])