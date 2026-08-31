"""
Loads the Dread forum archive from parquet. Globs every file matching
each pattern, so this works with your 3 sample files today and the
full ~20-file export later without any code change.
"""

from __future__ import annotations

import glob
import os

import pandas as pd

from . import config


def _load_all(directory: str, pattern: str, columns: list[str] | None = None) -> pd.DataFrame:
    paths = sorted(glob.glob(os.path.join(directory, pattern)))
    if not paths:
        raise FileNotFoundError(f"No files matching {pattern!r} in {directory}")
    frames = [pd.read_parquet(p, columns=columns) for p in paths]
    return pd.concat(frames, ignore_index=True)


def load_users(data_dir: str = config.DREAD_DATA_DIR) -> pd.DataFrame:
    cols = ["username", "has_key", "fingerprint", "emails"]
    df = _load_all(data_dir, config.DREAD_USERS_GLOB, columns=cols)
    return df.drop_duplicates(subset="username")


def load_posts(data_dir: str = config.DREAD_DATA_DIR) -> pd.DataFrame:
    cols = ["post_key", "title", "author", "subdread", "posted_date", "body_text"]
    return _load_all(data_dir, config.DREAD_POSTS_GLOB, columns=cols)


def load_comments(data_dir: str = config.DREAD_DATA_DIR) -> pd.DataFrame:
    cols = ["comment_key", "post_key", "parent_comment_key", "author", "posted_date", "body_text"]
    return _load_all(data_dir, config.DREAD_COMMENTS_GLOB, columns=cols)


if __name__ == "__main__":
    users = load_users()
    posts = load_posts()
    comments = load_comments()
    print("users:", len(users), "| posts:", len(posts), "| comments:", len(comments))
