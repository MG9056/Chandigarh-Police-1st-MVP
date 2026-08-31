"""
Loads the Elliptic++ actor-level data: wallet classifications
(address, class) and the address-address edge list (input_address,
output_address). No amounts/timestamps exist at this level of the
dataset (that's the tx-level files, not provided here) — the graph
value here is topology + the illicit/licit/unknown label, not flow
amounts.

Every function here works directly off real rows from disk. Nothing
in this file invents an edge or a label.
"""

from __future__ import annotations

import glob
import os

import pandas as pd
import networkx as nx

from . import config


def _find_one(directory: str, pattern: str) -> str:
    matches = sorted(glob.glob(os.path.join(directory, pattern)))
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern!r} in {directory}")
    return matches[0]


def load_wallets(data_dir: str = config.ELLIPTIC_DATA_DIR) -> pd.DataFrame:
    """Returns DataFrame[address, class] — class is 1/2/3 (illicit/licit/unknown)."""
    path = _find_one(data_dir, config.ELLIPTIC_WALLETS_GLOB)
    df = pd.read_csv(path, usecols=["address", "class"])
    df["class"] = df["class"].astype(int)
    return df.drop_duplicates(subset="address")


def load_edges(data_dir: str = config.ELLIPTIC_DATA_DIR) -> pd.DataFrame:
    """Returns DataFrame[input_address, output_address]."""
    path = _find_one(data_dir, config.ELLIPTIC_EDGES_GLOB)
    return pd.read_csv(path, usecols=["input_address", "output_address"]).dropna()


def build_illicit_focused_subgraph(
    max_nodes: int = config.MAX_ELLIPTIC_NODES,
    data_dir: str = config.ELLIPTIC_DATA_DIR,
) -> dict:
    """
    Real Elliptic++ data, filtered down to something a browser can render.

    Blockchain address graphs have one dominant giant component (in this
    dataset, ~21k of the ~26k illicit-touching addresses) that's too
    tangled to render meaningfully, plus hundreds of small, naturally
    self-contained components. Rather than thinning the giant component
    into a sparse skeleton (which loses the actual cluster structure —
    tried it, ended up with 120 nodes and 22 edges), this takes whole
    small components — real, fully-formed sub-clusters from the data —
    greedily by size until the node budget is used, favoring components
    with a higher illicit fraction when sizes are close. Every node/edge
    kept is exactly as it appears in the source CSVs.

    Returns {"nodes": [...], "edges": [...]}.
    """
    wallets = load_wallets(data_dir)
    edges = load_edges(data_dir)

    class_by_addr = dict(zip(wallets.address, wallets["class"]))
    illicit = set(wallets[wallets["class"] == config.ILLICIT_CLASS].address)

    touching = edges[
        edges.input_address.isin(illicit) | edges.output_address.isin(illicit)
    ]
    if touching.empty:
        return {"nodes": [], "edges": []}

    g = nx.from_pandas_edgelist(
        touching, source="input_address", target="output_address"
    )
    g.remove_edges_from(nx.selfloop_edges(g))

    def illicit_fraction(component: set) -> float:
        return sum(1 for n in component if class_by_addr.get(n) == config.ILLICIT_CLASS) / len(component)

    components = sorted(
        nx.connected_components(g),
        key=lambda c: (len(c), illicit_fraction(c)),
        reverse=True,
    )

    kept_nodes: set = set()
    kept_subgraphs = []
    for comp in components:
        if len(kept_nodes) + len(comp) > max_nodes:
            continue
        kept_nodes |= comp
        kept_subgraphs.append(comp)
        if len(kept_nodes) >= max_nodes * 0.9:
            break

    degree = dict(g.degree(kept_nodes))
    nodes = [
        {
            "address": addr,
            "class": class_by_addr.get(addr, config.UNKNOWN_CLASS),
            "degree": degree.get(addr, 0),
        }
        for addr in kept_nodes
    ]
    kept_edges = [
        (u, v) for u, v in g.edges(kept_nodes) if u in kept_nodes and v in kept_nodes
    ]

    return {"nodes": nodes, "edges": kept_edges}


if __name__ == "__main__":
    data = build_illicit_focused_subgraph()
    print("nodes:", len(data["nodes"]))
    print("edges:", len(data["edges"]))
    illicit_ct = sum(1 for n in data["nodes"] if n["class"] == config.ILLICIT_CLASS)
    print("illicit-labeled among kept nodes:", illicit_ct)
