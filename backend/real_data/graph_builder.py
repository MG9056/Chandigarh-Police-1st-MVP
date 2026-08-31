"""
Combines the Elliptic++ subgraph (elliptic_loader) and the Dread
correlation signals (intelligence.py) into the exact {nodes, links}
shape NetworkGraph.jsx already renders — same node fields
(id/label/group/risk_level/notes) and link fields (source/target/value/
type/confidence) as graph_adapter.py's synthetic output, so the
frontend needs zero changes to consume this.

Node id namespacing: "wallet:<address>", "account:<username>",
"market:<subdread>" — keeps the two source datasets from colliding if
an address string and a username string ever happened to match.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict

from . import config, dread_loader, elliptic_loader, intelligence

CACHE_PATH = os.path.join(config.CACHE_DIR, "network_real.json")
CACHE_TTL_SECONDS = 6 * 60 * 60  # rebuild at most every 6h; data only changes when you drop in new files


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
    note = f"Dread forum account."
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


def build_real_network_data(
    elliptic_dir: str = config.ELLIPTIC_DATA_DIR,
    dread_dir: str = config.DREAD_DATA_DIR,
) -> dict:
    # ---- Elliptic++ side ----
    ell = elliptic_loader.build_illicit_focused_subgraph(
        max_nodes=config.MAX_ELLIPTIC_NODES, data_dir=elliptic_dir
    )
    wallet_addrs = {n["address"] for n in ell["nodes"]}

    nodes = [_wallet_node(n["address"], n["class"], n["degree"]) for n in ell["nodes"]]
    links = [
        {"source": f"wallet:{u}", "target": f"wallet:{v}", "value": 1, "type": "observed"}
        for u, v in ell["edges"]
    ]

    # ---- Dread side ----
    users = dread_loader.load_users(dread_dir)
    posts = dread_loader.load_posts(dread_dir)
    comments = dread_loader.load_comments(dread_dir)

    clusters = intelligence.find_pgp_alias_clusters(users)
    replies = intelligence.build_reply_graph(comments, top_n=config.MAX_DREAD_ACCOUNT_NODES)
    markets = intelligence.build_market_edges(posts, top_authors=config.MAX_DREAD_ACCOUNT_NODES)
    mentions = intelligence.extract_wallet_mentions(posts, comments)

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
    used_markets = set(
        sorted(market_totals, key=market_totals.get, reverse=True)[: config.MAX_MARKET_NODES]
    )
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

    return {"nodes": nodes, "links": links}


def get_cached_or_build(force: bool = False) -> dict:
    if not force and os.path.exists(CACHE_PATH):
        age = time.time() - os.path.getmtime(CACHE_PATH)
        if age < CACHE_TTL_SECONDS:
            with open(CACHE_PATH) as f:
                return json.load(f)

    data = build_real_network_data()
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f)
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
