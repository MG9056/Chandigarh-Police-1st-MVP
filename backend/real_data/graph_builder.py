"""
Combines a real Elliptic++ illicit-wallet cluster and real Dread
correlation signals (intelligence.py) into the exact {nodes, links}
shape NetworkGraph.jsx already renders — same node fields
(id/label/group/risk_level/notes) and link fields (source/target/value/
type/confidence) as graph_adapter.py's synthetic output, so the
frontend needs zero changes to consume this.

All raw data comes from loader.RealDataLoader, which auto-detects
Elliptic++ vs Dread files by schema rather than filename — see
loader.py's module docstring for why.

Node id namespacing: "wallet:<address>", "account:<username>",
"market:<subdread>" — keeps the two source datasets from colliding if
an address string and a username string ever happened to match.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict

import networkx as nx
import pandas as pd

from . import config, intelligence
from .loader import RealDataLoader

CACHE_PATH = os.path.join(config.CACHE_DIR, "network_real.json")
CACHE_TTL_SECONDS = 6 * 60 * 60  # rebuild at most every 6h; data only changes when you drop in new files
# Bump whenever build_real_network_data()'s output shape changes. See
# the identical mechanism (and the bug it fixes) in geo_signals.py's
# CACHE_SCHEMA_VERSION — a schema change without this bumped means a
# stale cache gets served forever with no error, since only the file's
# age is otherwise checked, never its shape.
CACHE_SCHEMA_VERSION = 1

_T0 = time.time()


def _log(msg: str) -> None:
    print(f"[graph_builder +{time.time() - _T0:.1f}s] {msg}", flush=True)


# --- Elliptic++ side: pick a real, self-contained illicit-touching
# cluster small enough to render, optionally enriched with real feature
# columns if a features file was found. ---------------------------------

def _illicit_focused_subgraph(loader: RealDataLoader, max_nodes: int = config.MAX_ELLIPTIC_NODES) -> dict:
    """
    Blockchain address graphs have one dominant giant component that's
    too tangled to render meaningfully, plus hundreds of small,
    naturally self-contained components. Rather than thinning the giant
    component into a sparse skeleton (tried it once — 120 nodes, 22
    edges, all the actual cluster structure lost), this takes whole
    small components — real, fully-formed sub-clusters — greedily by
    size until the node budget is used, favoring components with a
    higher illicit fraction when sizes are close.

    Returns {"nodes": [...], "edges": [...]}, each node carrying its
    real address, class label, computed degree, and (if a features file
    was found) a "features" dict with every real Elliptic++ feature
    column, verbatim.
    """
    wallets = loader.wallets
    edges = loader.address_edges
    features = loader.wallet_features

    class_by_addr = dict(zip(wallets.address, wallets["class"]))
    illicit = set(wallets[wallets["class"] == config.ILLICIT_CLASS].address)
    _log(f"{len(illicit)} illicit-labeled wallets. Filtering edge list...")

    touching = edges[edges.input_address.isin(illicit) | edges.output_address.isin(illicit)]
    _log(f"{len(touching)} edges touch an illicit wallet.")
    if touching.empty:
        return {"nodes": [], "edges": []}

    _log("building graph (can be slow at full Elliptic++ scale)...")
    g = nx.from_pandas_edgelist(touching, source="input_address", target="output_address")
    g.remove_edges_from(nx.selfloop_edges(g))
    _log(f"graph built: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges. Finding connected components...")

    def illicit_fraction(component: set) -> float:
        return sum(1 for n in component if class_by_addr.get(n) == config.ILLICIT_CLASS) / len(component)

    components = sorted(nx.connected_components(g), key=lambda c: (len(c), illicit_fraction(c)), reverse=True)
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

    def feature_dict(addr: str) -> dict | None:
        if features is None or addr not in features.index:
            return None
        row = features.loc[addr]
        out = {}
        for col, val in row.items():
            if pd.isna(val):
                out[col] = None
            elif hasattr(val, "item"):
                out[col] = val.item()
            else:
                out[col] = val
        return out

    nodes = []
    for addr in kept_nodes:
        node = {"address": addr, "class": class_by_addr.get(addr, config.UNKNOWN_CLASS), "degree": degree.get(addr, 0)}
        feat = feature_dict(addr)
        if feat:
            node["features"] = feat
        nodes.append(node)

    kept_edges = [(u, v) for u, v in g.edges(kept_nodes) if u in kept_nodes and v in kept_nodes]
    return {"nodes": nodes, "edges": kept_edges}


def _wallet_node(address: str, cls: int, degree: int) -> dict:
    risk = {
        config.ILLICIT_CLASS: "High",
        config.LICIT_CLASS: "Low",
        config.UNKNOWN_CLASS: "Unscored",
    }.get(cls, "Unscored")
    label_class = {config.ILLICIT_CLASS: "illicit", config.LICIT_CLASS: "licit", config.UNKNOWN_CLASS: "unknown"}.get(cls, "unknown")
    return {
        "id": f"wallet:{address}",
        "label": address[:10] + "…",
        "group": "wallet",
        "risk_level": risk,
        "notes": f"Elliptic++ wallet — labeled {label_class}, on-chain degree {degree} in this cluster.",
    }


def _account_node(username: str, market_posts: dict, mention_count: int) -> dict:
    top_market = max(market_posts, key=market_posts.get) if market_posts else None
    note = "Dread forum account."
    if top_market:
        note += f" Most active on r/{top_market} ({market_posts[top_market]} posts)."
    if mention_count:
        note += f" Mentioned {mention_count} wallet-address-shaped string(s) in posts/comments."
    return {
        "id": f"account:{username}",
        "label": username,
        "group": "account",
        "risk_level": "Unscored",
        "notes": note,
    }


def _market_node(subdread: str) -> dict:
    return {
        "id": f"market:{subdread}",
        "label": subdread,
        "group": "market",
        "risk_level": "Unscored",
        "notes": "Dread subdread (board) — real posting activity.",
    }


def build_real_network_data(data_paths: str | list[str] | None = None) -> dict:
    loader = RealDataLoader(data_paths)
    _log(f"loader classification: {loader.summary()}")

    # ---- Elliptic++ side ----
    _log("=== starting Elliptic++ side ===")
    ell = _illicit_focused_subgraph(loader, max_nodes=config.MAX_ELLIPTIC_NODES)
    wallet_addrs = {n["address"] for n in ell["nodes"]}
    _log(f"=== Elliptic++ side done: {len(ell['nodes'])} wallet nodes ===")

    nodes = [_wallet_node(n["address"], n["class"], n["degree"]) for n in ell["nodes"]]
    links = [
        {"source": f"wallet:{u}", "target": f"wallet:{v}", "value": 1, "type": "observed"}
        for u, v in ell["edges"]
    ]

    # ---- Dread side ----
    _log("=== starting Dread side ===")
    users = loader.users
    posts = loader.posts
    comments = loader.comments
    _log(f"loaded {len(users)} users, {len(posts)} posts, {len(comments)} comments.")

    _log("finding PGP/email alias clusters...")
    clusters = intelligence.find_pgp_alias_clusters(users)
    _log(f"found {len(clusters)} alias clusters. Building reply graph...")
    replies = intelligence.build_reply_graph(comments, top_n=config.MAX_DREAD_ACCOUNT_NODES)
    _log(f"found {len(replies)} reply pairs. Building market edges...")
    markets = intelligence.build_market_edges(posts, top_authors=config.MAX_DREAD_ACCOUNT_NODES)
    _log(f"found {len(markets)} account-market edges. Extracting wallet mentions from text...")
    mentions = intelligence.extract_wallet_mentions(posts, comments)
    _log(f"extracted {len(mentions)} wallet-address mentions. Assembling combined graph...")

    # Pick which Dread accounts make the node budget: alias-cluster
    # members always included (they're the strongest signal), then fill
    # remaining budget with whoever bridges to a real Elliptic++ wallet,
    # then top reply/market participants by volume.
    bridging_authors = {m["author"] for m in mentions if m["address"] in wallet_addrs}
    cluster_members = {u for c in clusters for u in c["members"]}
    reply_authors = {a for a, b, _ in replies} | {b for a, b, _ in replies}
    market_authors = {a for a, _, _ in markets}

    account_order = list(cluster_members) + list(bridging_authors) + list(reply_authors) + list(market_authors)
    seen = set()
    selected_accounts = []
    for a in account_order:
        if a not in seen:
            seen.add(a)
            selected_accounts.append(a)
        if len(selected_accounts) >= config.MAX_DREAD_ACCOUNT_NODES:
            break
    selected_set = set(selected_accounts)

    market_posts_by_author: dict[str, dict] = defaultdict(dict)
    for author, subdread, count in markets:
        market_posts_by_author[author][subdread] = count

    mention_count_by_author: dict[str, int] = defaultdict(int)
    for m in mentions:
        mention_count_by_author[m["author"]] += 1

    for username in selected_accounts:
        nodes.append(_account_node(username, market_posts_by_author.get(username, {}), mention_count_by_author.get(username, 0)))

    # Market nodes: only ones actually posted-to by a selected account,
    # capped to the highest-traffic boards so the graph doesn't drown in
    # long-tail subdreads a single account posted to once.
    market_totals: dict[str, int] = defaultdict(int)
    for author, subdread, count in markets:
        if author in selected_set:
            market_totals[subdread] += count
    used_markets = set(sorted(market_totals, key=market_totals.get, reverse=True)[: config.MAX_MARKET_NODES])
    for subdread in used_markets:
        nodes.append(_market_node(subdread))

    # OBSERVED: reply edges between selected accounts
    for a, b, count in replies:
        if a in selected_set and b in selected_set:
            links.append({"source": f"account:{a}", "target": f"account:{b}", "value": int(count), "type": "observed"})

    # OBSERVED: account -> market posting edges
    for author, subdread, count in markets:
        if author in selected_set and subdread in used_markets:
            links.append({"source": f"account:{author}", "target": f"market:{subdread}", "value": int(count), "type": "observed"})

    # INFERRED: PGP/email alias clusters (pairwise within each cluster)
    for c in clusters:
        members = [m for m in c["members"] if m in selected_set]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                links.append({
                    "source": f"account:{members[i]}", "target": f"account:{members[j]}",
                    "value": 1, "type": "inferred", "confidence": config.CONFIDENCE_PGP_ALIAS,
                })

    # INFERRED: bridge from Dread account to a real Elliptic++ wallet it mentioned
    seen_bridges = set()
    for m in mentions:
        if m["author"] in selected_set and m["address"] in wallet_addrs:
            key = (m["author"], m["address"])
            if key in seen_bridges:
                continue
            seen_bridges.add(key)
            links.append({
                "source": f"account:{m['author']}", "target": f"wallet:{m['address']}",
                "value": 1, "type": "inferred", "confidence": config.CONFIDENCE_WALLET_MENTION,
            })

    return {"cache_schema_version": CACHE_SCHEMA_VERSION, "nodes": nodes, "links": links}


def get_cached_or_build(force: bool = False) -> dict:
    if not force and os.path.exists(CACHE_PATH):
        try:
            age = time.time() - os.path.getmtime(CACHE_PATH)
            if age < CACHE_TTL_SECONDS:
                with open(CACHE_PATH) as f:
                    cached = json.load(f)
                if cached.get("cache_schema_version") == CACHE_SCHEMA_VERSION:
                    _log(f"serving cached result ({age:.0f}s old, schema v{CACHE_SCHEMA_VERSION}).")
                    return cached
                _log(f"cached file is schema v{cached.get('cache_schema_version')!r}, code expects v{CACHE_SCHEMA_VERSION} — ignoring stale cache and rebuilding.")
        except json.JSONDecodeError:
            _log("cache file exists but isn't valid JSON (likely a truncated write from an earlier crash) — ignoring it and rebuilding.")

    _log("no fresh cache — building from scratch (this can take several minutes on the full dataset; run `python -m real_data.graph_builder` directly to watch progress).")
    data = build_real_network_data()
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f)
    _log(f"=== ALL DONE: {len(data['nodes'])} nodes, {len(data['links'])} links. Cached to {CACHE_PATH} ===")
    return data


if __name__ == "__main__":
    import time as _t

    t0 = _t.time()
    data = build_real_network_data()
    print(f"built in {_t.time() - t0:.1f}s")
    print("nodes:", len(data["nodes"]))
    print("links:", len(data["links"]))
    by_group = defaultdict(int)
    for n in data["nodes"]:
        by_group[n["group"]] += 1
    print("by group:", dict(by_group))
    by_type = defaultdict(int)
    for l in data["links"]:
        by_type[l["type"]] += 1
    print("by link type:", dict(by_type))