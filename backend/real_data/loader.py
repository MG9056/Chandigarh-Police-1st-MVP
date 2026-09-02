"""
A single intelligent loader: point it at one or more directories (or
individual files) containing ANY mix of Elliptic++ CSVs and Dread forum
parquet files — any combination, any filenames, any subset, mixed
together in one folder or split across several — and it figures out
what each file actually is by inspecting its real columns (and, when
column names alone are ambiguous, sampling real values), cleans it
appropriately, and merges same-kind files together automatically (your
20 Dread `posts-*.parquet` files all become one `posts` dataframe;
`wallets_classes.csv` and `sample_wallets.csv` sitting in the same
folder both become part of `wallets` rather than needing one to be
picked over the other by filename priority).

This replaces the old elliptic_loader.py + dread_loader.py, which
required exact/fuzzy filename matches (wallets_classes.csv specifically,
AddrAddr_edgelist.csv specifically, etc.) — brittle, and it broke once
already when this pipeline was extended (see the git history / earlier
conversation: `wallets_features.csv` vs `sample_wallets.csv` sorting
ambiguity). Nothing here depends on a filename at all.

Usage:
    from real_data.loader import RealDataLoader
    loader = RealDataLoader()  # defaults to scanning config.REAL_DATA_ROOT recursively
    loader.summary()           # prints what it found and how it classified each file

    wallets = loader.wallets              # DataFrame[address, class]  (1/2/3 = illicit/licit/unknown)
    edges = loader.address_edges          # DataFrame[input_address, output_address]
    features = loader.wallet_features     # DataFrame indexed by address, every real feature column, or None
    users = loader.users                  # DataFrame[username, has_key, fingerprint, emails, ...]
    posts = loader.posts                  # DataFrame[post_key, author, subdread, body_text, ...]
    comments = loader.comments            # DataFrame[comment_key, parent_comment_key, author, body_text, ...]

A file whose schema doesn't match anything this loader knows about is
skipped with a logged reason — it never takes down the whole pipeline.
"""

from __future__ import annotations

import glob
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd

from . import config

_T0 = time.time()


def _log(msg: str) -> None:
    print(f"[loader +{time.time() - _T0:.1f}s] {msg}", flush=True)


BTC_ADDRESS_RE = re.compile(r"^(?:bc1[a-z0-9]{11,71}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
TX_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# --- Recognized dataset kinds -------------------------------------------------
WALLET_CLASSES = "wallet_classes"
WALLET_FEATURES = "wallet_features"
ADDRESS_EDGES = "address_edges"
TX_CLASSES = "tx_classes"        # detected + stored; not currently consumed downstream
TX_FEATURES = "tx_features"      # detected + stored; not currently consumed downstream
TX_EDGES = "tx_edges"            # detected + stored; not currently consumed downstream
ADDR_TX_EDGES = "addr_tx_edges"  # detected + stored; not currently consumed downstream
TX_ADDR_EDGES = "tx_addr_edges"  # detected + stored; not currently consumed downstream
DREAD_USERS = "dread_users"
DREAD_POSTS = "dread_posts"
DREAD_COMMENTS = "dread_comments"
UNKNOWN = "unknown"


@dataclass
class ClassifiedFile:
    path: str
    kind: str
    meta: dict = field(default_factory=dict)


# --- Schema inspection (cheap — never loads a full file just to classify it) --

def _peek_columns(path: str) -> list[str]:
    if path.lower().endswith(".parquet"):
        import pyarrow.parquet as pq
        return [f.name for f in pq.ParquetFile(path).schema_arrow]
    return list(pd.read_csv(path, nrows=0).columns)


def _peek_sample(path: str, columns: list[str], n: int = 200) -> pd.DataFrame:
    cols = columns[:5]
    if path.lower().endswith(".parquet"):
        return pd.read_parquet(path, columns=cols).head(n)
    return pd.read_csv(path, nrows=n, usecols=cols)


def _match_rate(series: pd.Series, pattern: re.Pattern, sample_size: int = 50) -> float:
    sample = series.dropna().astype(str).head(sample_size)
    if len(sample) == 0:
        return 0.0
    return sample.apply(lambda v: bool(pattern.fullmatch(v))).mean()


def _looks_like_addresses(series: pd.Series) -> bool:
    return _match_rate(series, BTC_ADDRESS_RE) >= 0.6


def _looks_like_tx_hashes(series: pd.Series) -> bool:
    return _match_rate(series, TX_HASH_RE) >= 0.6


def classify_file(path: str) -> list[ClassifiedFile]:
    """
    Figures out what a file is from its schema (and, where that's
    ambiguous, a small content sample). Returns a list because one file
    can legitimately be more than one thing — e.g.
    wallets_features_classes_combined.csv is simultaneously a classes
    file (id + class) and a features file (id + everything else).
    Returns [] (not an exception) for anything unrecognized, so one
    stray or irrelevant file in the data directory never takes down
    ingestion of everything else.
    """
    try:
        cols = _peek_columns(path)
    except Exception as e:
        _log(f"  {os.path.basename(path)}: couldn't read schema ({e}) — skipping.")
        return []

    if not cols:
        return []

    lower = {c.lower(): c for c in cols}
    colset = set(lower)

    # --- Dread forum tables: identified by column names specific enough
    # that there's no realistic overlap with an Elliptic++ export.
    if {"comment_key", "parent_comment_key"} <= colset:
        return [ClassifiedFile(path, DREAD_COMMENTS, {"columns": cols})]
    if "post_key" in colset and ("subdread" in colset or "body_text" in colset):
        return [ClassifiedFile(path, DREAD_POSTS, {"columns": cols})]
    if "username" in colset and ({"has_key", "fingerprint", "emails"} & colset):
        return [ClassifiedFile(path, DREAD_USERS, {"columns": cols})]

    # --- Elliptic++ tables. The id column might be an address or a tx
    # hash — Elliptic++'s own files don't consistently name it, so this
    # is resolved by sampling real values further down, never assumed
    # from the column name alone.
    id_col = None
    for candidate in ("address", "wallet_address", "txid", "tx_id", "tx_hash", "id"):
        if candidate in lower:
            id_col = lower[candidate]
            break
    if id_col is None:
        id_col = cols[0]  # last resort: treat the first column as the id, same fallback the old loader used

    # Two-column files are edge lists in this dataset family. Classify
    # by what each column's VALUES look like, not the column names —
    # Elliptic++'s AddrAddr/AddrTx/TxAddr/txs_edgelist files all just
    # call their columns something generic, so name-matching alone
    # can't tell them apart.
    if len(cols) == 2:
        try:
            sample = _peek_sample(path, cols)
        except Exception as e:
            _log(f"  {os.path.basename(path)}: couldn't sample content ({e}) — skipping.")
            return []
        a, b = cols[0], cols[1]
        a_addr, b_addr = _looks_like_addresses(sample[a]), _looks_like_addresses(sample[b])
        a_tx, b_tx = _looks_like_tx_hashes(sample[a]), _looks_like_tx_hashes(sample[b])
        meta = {"source_col": a, "target_col": b}
        if a_addr and b_addr:
            return [ClassifiedFile(path, ADDRESS_EDGES, meta)]
        if a_addr and b_tx:
            return [ClassifiedFile(path, ADDR_TX_EDGES, meta)]
        if a_tx and b_addr:
            return [ClassifiedFile(path, TX_ADDR_EDGES, meta)]
        if a_tx and b_tx:
            return [ClassifiedFile(path, TX_EDGES, meta)]
        # Two columns but content didn't look like either — could still
        # be a tiny classes file (id + class); fall through to the
        # class-column check below rather than giving up here.

    results: list[ClassifiedFile] = []
    has_class = "class" in lower
    is_wide = len(cols) > 5

    if has_class:
        class_col = lower["class"]
        try:
            sample = _peek_sample(path, [id_col, class_col])
            addr_id = _looks_like_addresses(sample[id_col])
            tx_id = _looks_like_tx_hashes(sample[id_col])
        except Exception:
            addr_id, tx_id = False, False
        if tx_id and not addr_id:
            results.append(ClassifiedFile(path, TX_CLASSES, {"id_col": id_col, "class_col": class_col}))
        else:
            # Defaults to wallet_classes on an inconclusive sample too —
            # that's what this pipeline actually consumes, and it's
            # logged so a wrong guess is visible rather than silent.
            if not addr_id and not tx_id:
                _log(f"  {os.path.basename(path)}: has a 'class' column but the id column didn't clearly look like an address or tx hash — assuming wallet_classes.")
            results.append(ClassifiedFile(path, WALLET_CLASSES, {"id_col": id_col, "class_col": class_col}))

    if is_wide:
        try:
            sample = _peek_sample(path, [id_col])
            addr_id = _looks_like_addresses(sample[id_col])
        except Exception:
            addr_id = True  # default matches this pipeline's primary use case (wallet features)
        exclude = [lower["class"]] if has_class else []
        kind = WALLET_FEATURES if addr_id else TX_FEATURES
        results.append(ClassifiedFile(path, kind, {"id_col": id_col, "exclude_cols": exclude}))

    return results


# --- Full-file loading + cleaning, once a file's kind is known ----------------

def _read_full(path: str, columns: list[str] | None = None) -> pd.DataFrame:
    if path.lower().endswith(".parquet"):
        return pd.read_parquet(path, columns=columns)
    return pd.read_csv(path, usecols=columns, low_memory=False)


def _clean_wallet_classes(cf: ClassifiedFile) -> pd.DataFrame:
    id_col, class_col = cf.meta["id_col"], cf.meta["class_col"]
    df = _read_full(cf.path, [id_col, class_col])
    df = df.rename(columns={id_col: "address", class_col: "class"})
    df["address"] = df["address"].astype(str)
    df["class"] = pd.to_numeric(df["class"], errors="coerce")
    df = df.dropna(subset=["class"])
    df["class"] = df["class"].astype(int)
    return df.drop_duplicates(subset="address")


def _clean_address_edges(cf: ClassifiedFile) -> pd.DataFrame:
    src, dst = cf.meta["source_col"], cf.meta["target_col"]
    df = _read_full(cf.path, [src, dst])
    df = df.rename(columns={src: "input_address", dst: "output_address"})
    df["input_address"] = df["input_address"].astype(str)
    df["output_address"] = df["output_address"].astype(str)
    return df.dropna()


def _clean_wallet_features(cf: ClassifiedFile) -> pd.DataFrame:
    df = _read_full(cf.path)  # need every column here — that's the point of this file
    id_col = cf.meta["id_col"]
    exclude = set(cf.meta.get("exclude_cols", []))
    df = df.rename(columns={id_col: "address"})
    df["address"] = df["address"].astype(str)
    keep = ["address"] + [c for c in df.columns if c not in ("address", *exclude)]
    return df[keep].drop_duplicates(subset="address")


_DREAD_USERS_WANTED = ["username", "has_key", "fingerprint", "emails"]
_DREAD_POSTS_WANTED = ["post_key", "title", "author", "subdread", "posted_date", "body_text"]
_DREAD_COMMENTS_WANTED = ["comment_key", "post_key", "parent_comment_key", "author", "posted_date", "body_text"]


def _clean_dread(cf: ClassifiedFile, wanted: list[str]) -> pd.DataFrame:
    available = [c for c in wanted if c in cf.meta.get("columns", wanted)]
    return _read_full(cf.path, available)


_CLEANERS = {
    WALLET_CLASSES: _clean_wallet_classes,
    ADDRESS_EDGES: _clean_address_edges,
    WALLET_FEATURES: _clean_wallet_features,
    DREAD_USERS: lambda cf: _clean_dread(cf, _DREAD_USERS_WANTED),
    DREAD_POSTS: lambda cf: _clean_dread(cf, _DREAD_POSTS_WANTED),
    DREAD_COMMENTS: lambda cf: _clean_dread(cf, _DREAD_COMMENTS_WANTED),
}

_DEDUP_KEY = {
    WALLET_CLASSES: "address",
    WALLET_FEATURES: "address",
    DREAD_USERS: "username",
    DREAD_POSTS: "post_key",
    DREAD_COMMENTS: "comment_key",
}


class RealDataLoader:
    """
    Scans `paths` (default: config.REAL_DATA_ROOT, recursively — so it
    doesn't matter whether Elliptic++ and Dread files are kept in
    separate subfolders, mixed in one folder, or renamed) and classifies
    every .csv/.parquet file it finds. Actual file reading is lazy —
    scanning just peeks schemas; a given dataset (e.g. `.wallet_features`)
    is only fully read the first time you access it.
    """

    def __init__(self, paths: str | list[str] | None = None):
        if paths is None:
            paths = [config.REAL_DATA_ROOT]
        elif isinstance(paths, str):
            paths = [paths]

        self._by_kind: dict[str, list[ClassifiedFile]] = defaultdict(list)
        self._cache: dict[str, pd.DataFrame | None] = {}
        self._scan(paths)

    def _scan(self, paths: list[str]) -> None:
        files: list[str] = []
        for p in paths:
            if os.path.isdir(p):
                files += glob.glob(os.path.join(p, "**", "*.csv"), recursive=True)
                files += glob.glob(os.path.join(p, "**", "*.parquet"), recursive=True)
            elif os.path.isfile(p):
                files.append(p)
            else:
                _log(f"path does not exist, skipping: {p}")

        _log(f"scanning {len(files)} file(s) under {paths}...")
        for f in files:
            classified = classify_file(f)
            if not classified:
                _log(f"  {os.path.basename(f)}: unrecognized schema — skipping.")
                continue
            for cf in classified:
                _log(f"  {os.path.basename(f)}: classified as {cf.kind}")
                self._by_kind[cf.kind].append(cf)

    def summary(self) -> dict[str, list[str]]:
        """What was found and how each file was classified — call this
        first when something's missing, before assuming a bug."""
        return {kind: [os.path.basename(cf.path) for cf in files] for kind, files in self._by_kind.items()}

    def _load_kind(self, kind: str) -> pd.DataFrame | None:
        if kind in self._cache:
            return self._cache[kind]

        files = self._by_kind.get(kind, [])
        if not files:
            self._cache[kind] = None
            return None

        cleaner = _CLEANERS[kind]
        frames = []
        for cf in files:
            _log(f"loading {os.path.basename(cf.path)} as {kind}...")
            frames.append(cleaner(cf))

        combined = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
        dedup_key = _DEDUP_KEY.get(kind)
        if dedup_key and dedup_key in combined.columns:
            combined = combined.drop_duplicates(subset=dedup_key)

        self._cache[kind] = combined
        return combined

    # --- Public accessors — same shapes the old elliptic_loader.py /
    # dread_loader.py returned, so graph_builder.py / intelligence.py /
    # geo_signals.py only need their import line changed. ---

    @property
    def wallets(self) -> pd.DataFrame:
        df = self._load_kind(WALLET_CLASSES)
        if df is None:
            raise FileNotFoundError(
                "No wallet-classes data found (need a file with an address-shaped id column "
                "and a small-integer 'class' column). Checked: " + str(dict(self.summary()))
            )
        return df

    @property
    def address_edges(self) -> pd.DataFrame:
        df = self._load_kind(ADDRESS_EDGES)
        if df is None:
            raise FileNotFoundError(
                "No address-address edge data found (need a 2-column file where both columns "
                "contain BTC-address-shaped values). Checked: " + str(dict(self.summary()))
            )
        return df

    @property
    def wallet_features(self) -> pd.DataFrame | None:
        """Indexed by 'address', every real feature column verbatim.
        None if no such file was found — features are optional."""
        df = self._load_kind(WALLET_FEATURES)
        return df.set_index("address") if df is not None else None

    @property
    def users(self) -> pd.DataFrame:
        df = self._load_kind(DREAD_USERS)
        if df is None:
            raise FileNotFoundError("No Dread users data found. Checked: " + str(dict(self.summary())))
        return df

    @property
    def posts(self) -> pd.DataFrame:
        df = self._load_kind(DREAD_POSTS)
        if df is None:
            raise FileNotFoundError("No Dread posts data found. Checked: " + str(dict(self.summary())))
        return df

    @property
    def comments(self) -> pd.DataFrame:
        df = self._load_kind(DREAD_COMMENTS)
        if df is None:
            raise FileNotFoundError("No Dread comments data found. Checked: " + str(dict(self.summary())))
        return df


if __name__ == "__main__":
    loader = RealDataLoader()
    print()
    print("=== classification summary ===")
    for kind, files in loader.summary().items():
        print(f"  {kind}: {files}")
    print()
    print("=== loading each recognized dataset ===")
    try:
        print("wallets:", len(loader.wallets), "rows")
    except FileNotFoundError as e:
        print("wallets: ", e)
    try:
        print("address_edges:", len(loader.address_edges), "rows")
    except FileNotFoundError as e:
        print("address_edges:", e)
    feat = loader.wallet_features
    print("wallet_features:", None if feat is None else f"{len(feat)} rows, {len(feat.columns)} columns")
    try:
        print("users:", len(loader.users), "rows")
    except FileNotFoundError as e:
        print("users:", e)
    try:
        print("posts:", len(loader.posts), "rows")
    except FileNotFoundError as e:
        print("posts:", e)
    try:
        print("comments:", len(loader.comments), "rows")
    except FileNotFoundError as e:
        print("comments:", e)