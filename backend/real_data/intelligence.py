"""
The "intelligence component": real correlation signals extracted from
the Dread archive, plus the one bridge that connects Dread to Elliptic++.

Every function returns edges backed by an actual matching fact in the
data (a shared PGP fingerprint, an actual reply, a regex-matched
address string) — nothing here is invented or randomly sampled. Each
function's docstring says exactly what real-world fact the edge
represents and how confident that fact should make an investigator,
mirroring the OBSERVED-vs-INFERRED split already used in
graph_adapter.py for the synthetic data.

Everything below is vectorized (pandas groupby/merge/str ops, not
python-level row loops) — this needs to stay usable once you drop in
the full ~20-file Dread export instead of the 3 samples.
"""

from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd

from . import config

_BTC_RE = re.compile(config.BTC_ADDRESS_REGEX)

# Not real actors — forum system accounts / tombstoned posts. Excluding
# these keeps the reply graph and market edges from centering on noise.
NOISE_AUTHORS = {"[deleted]", "AutoModerator", "[removed]", None}


def _clean_authors(df: pd.DataFrame, col: str = "author") -> pd.DataFrame:
    return df[~df[col].isin(NOISE_AUTHORS) & df[col].notna()]


def find_pgp_alias_clusters(users: pd.DataFrame) -> list[dict]:
    """
    INFERRED, high confidence: two Dread usernames that share a PGP key
    fingerprint or a verified email are, as a matter of cryptographic
    fact, controlled by whoever holds that private key — this is the
    same kind of evidence investigators already use to link forum
    aliases in the real world, not a fuzzy string-similarity guess.

    Returns a list of {"members": [usernames], "reason": "fingerprint"|"email", "value": ...}
    """
    clusters = []

    by_fp = users.dropna(subset=["fingerprint"]).groupby("fingerprint")["username"].apply(set)
    for fp, members in by_fp.items():
        if len(members) > 1:
            clusters.append({"members": sorted(members), "reason": "shared_pgp_fingerprint", "value": fp})

    email_groups: dict[str, set[str]] = defaultdict(set)
    with_emails = users[users["emails"].apply(lambda x: hasattr(x, "__len__") and len(x) > 0)]
    for username, emails in zip(with_emails.username, with_emails.emails):
        for email in emails:
            if email:
                email_groups[email].add(username)
    for email, members in email_groups.items():
        if len(members) > 1:
            clusters.append({"members": sorted(members), "reason": "shared_email", "value": email})

    return clusters


def build_reply_graph(comments: pd.DataFrame, top_n: int = 60) -> list[tuple[str, str, int]]:
    """
    OBSERVED: A replied directly to a comment authored by B. This is a
    real recorded interaction, not an inference — same status as a
    transaction edge in the Elliptic++ graph. Returns the `top_n`
    highest-volume (author, parent_author) pairs as (a, b, count).

    Implemented as a self-merge (comment -> its parent's author) rather
    than a row-by-row loop, so it stays fast at full dataset scale.
    """
    replies = comments.dropna(subset=["parent_comment_key"])[["comment_key", "parent_comment_key", "author"]]
    parents = comments[["comment_key", "author"]].rename(
        columns={"comment_key": "parent_comment_key", "author": "parent_author"}
    )
    merged = replies.merge(parents, on="parent_comment_key", how="inner")
    merged = merged[merged.author != merged.parent_author]
    merged = _clean_authors(merged, "author")
    merged = _clean_authors(merged, "parent_author")

    pair = pd.DataFrame({
        "a": merged[["author", "parent_author"]].min(axis=1),
        "b": merged[["author", "parent_author"]].max(axis=1),
    })
    counts = pair.value_counts().reset_index(name="count").head(top_n)
    return list(counts[["a", "b", "count"]].itertuples(index=False, name=None))


def build_market_edges(posts: pd.DataFrame, top_authors: int = 60) -> list[tuple[str, str, int]]:
    """
    OBSERVED: author actually posted on this subdread. Returns
    (author, subdread, post_count) for the most active real authors, so
    the market nodes in the graph connect to actual vendors/posters
    rather than a hand-picked example.
    """
    valid = _clean_authors(posts.dropna(subset=["author", "subdread"]))
    top_author_set = set(valid.author.value_counts().head(top_authors).index)
    valid = valid[valid.author.isin(top_author_set)]
    counts = valid.groupby(["author", "subdread"]).size().reset_index(name="count")
    return list(counts.itertuples(index=False, name=None))


def extract_wallet_mentions(posts: pd.DataFrame, comments: pd.DataFrame) -> list[dict]:
    """
    Regex-extracts BTC-address-shaped strings out of real post/comment
    body text using vectorized pandas .str.findall(). Returns one row
    per (author, address, source) mention — every mention is an actual
    substring found in an actual post or comment, keyed by the real
    post_key/comment_key so it's auditable.

    This does NOT confirm wallet ownership — someone posting an address
    (their own, a scammer's, a donation ask) is a weaker signal than a
    PGP key match, which is why callers should mark links built from
    this as INFERRED with moderate confidence, same as
    CONFIDENCE_WALLET_MENTION in config.py.
    """
    mentions = []

    for df, key_col, source in [(posts, "post_key", "post"), (comments, "comment_key", "comment")]:
        valid = _clean_authors(df.dropna(subset=["body_text", "author"]))
        found = valid.body_text.str.findall(_BTC_RE)
        hit_mask = found.str.len() > 0
        if not hit_mask.any():
            continue
        exploded = pd.DataFrame({
            "author": valid.loc[hit_mask, "author"],
            "source_key": valid.loc[hit_mask, key_col],
            "address": found[hit_mask],
        }).explode("address").drop_duplicates()
        exploded["source"] = source
        mentions.extend(exploded.to_dict("records"))

    return mentions


if __name__ == "__main__":
    import time
    from .loader import RealDataLoader

    loader = RealDataLoader()
    users = loader.users
    posts = loader.posts
    comments = loader.comments

    t0 = time.time()
    clusters = find_pgp_alias_clusters(users)
    replies = build_reply_graph(comments)
    markets = build_market_edges(posts)
    mentions = extract_wallet_mentions(posts, comments)
    print(f"ran in {time.time() - t0:.1f}s")

    print("PGP/email alias clusters:", len(clusters))
    for c in clusters[:5]:
        print(" ", c)
    print("top reply pairs:", len(replies), replies[:3])
    print("author->market edges:", len(markets), markets[:3])
    print("wallet mentions extracted:", len(mentions))