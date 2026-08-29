"""
Workstream A (entity resolution) — Piece 1: username/identifier signals.

Deterministic string-similarity signal only. No ML, no other signal types
(bio, platform, behavior) yet — those are separate pieces, combined later
in a weighted score per workplan §9.5. This module answers one narrow
question: "how similar do these two identifiers LOOK", nothing else.

IMPORTANT: this signal alone is known to be unreliable — it will score
`john123` vs `john124` deceptively high even though they're unrelated
people (see ground_truth "decoy" in synthetic_data.py). Combining via
max() (see username_similarity()) makes this WORSE, not better, in
isolation: a single strong string-similarity signal is enough to produce
a high score here. That's a deliberate tradeoff — max() is tuned to
minimize missed matches (recall) at this stage, treating a high score as
"worth a human/other-signal look", not "confirmed same entity". Cutting
false positives is §9.5's job, once bio/platform/behavior signals are
combined with this one.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler


def _normalize(identifier: str) -> str:
    """Lowercase and strip separators (_, -, .) so 'abc123' and '123_abc'
    are compared on their actual characters, not punctuation noise."""
    return re.sub(r"[_\-.]", "", identifier.lower())


def _common_affix_score(a: str, b: str) -> float:
    """Fraction of the shorter string's length covered by a shared
    prefix + shared suffix. Catches cases like 'john123'/'john124' where
    the middle differs but the ends match strongly."""
    if not a or not b:
        return 0.0
    prefix_len = 0
    for x, y in zip(a, b):
        if x != y:
            break
        prefix_len += 1
    suffix_len = 0
    for x, y in zip(reversed(a), reversed(b)):
        if x != y:
            break
        suffix_len += 1
    shorter = min(len(a), len(b))
    # avoid double-counting overlap on very short/near-identical strings
    covered = min(prefix_len + suffix_len, shorter)
    return covered / shorter


def _ngram_overlap(a: str, b: str, n: int = 2) -> float:
    """Jaccard overlap of character n-grams. Unlike Levenshtein/Jaro-Winkler,
    this is ORDER-INSENSITIVE — it catches simple rotations/reorderings
    like 'abc123' vs '123abc', which position-sensitive metrics miss
    entirely (every character sits in a different position, so those
    metrics score the pair near 0 despite it being an obvious match to a
    human)."""
    def ngrams(s):
        return set(s[i:i + n] for i in range(len(s) - n + 1)) if len(s) >= n else {s}
    ga, gb = ngrams(a), ngrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def username_similarity(identifier_a: str, identifier_b: str) -> dict:
    """
    Returns a dict (not just a float) so the caller can see WHICH signal
    drove the score — needed later for the "evidence explaining the
    score" the workplan asks for in §9's example output.
    """
    norm_a, norm_b = _normalize(identifier_a), _normalize(identifier_b)

    levenshtein = fuzz.ratio(norm_a, norm_b) / 100.0
    jaro_winkler = JaroWinkler.normalized_similarity(norm_a, norm_b)
    affix = _common_affix_score(norm_a, norm_b)
    ngram = _ngram_overlap(norm_a, norm_b)

    # Combine via max(), not average. These four signals catch DIFFERENT
    # failure modes (order-sensitive vs. order-insensitive string
    # similarity) — averaging lets three signals that correctly score ~0
    # on a rotation (e.g. 'abc123' vs '123abc') drag down the one signal
    # (n-grams) that correctly caught it. max() means: if ANY one of
    # these deterministic signals is confident, that's enough to flag
    # this as a candidate pair worth a human's attention — it does NOT
    # mean the pair is confirmed the same entity, just that it's worth
    # surfacing. Confirming still requires the other signal types
    # (bio, platform, behavior) from later pieces.
    combined = max(levenshtein, jaro_winkler, affix, ngram)

    return {
        "identifier_a": identifier_a,
        "identifier_b": identifier_b,
        "levenshtein": round(levenshtein, 3),
        "jaro_winkler": round(jaro_winkler, 3),
        "common_affix": round(affix, 3),
        "ngram_overlap": round(ngram, 3),
        "username_similarity": round(combined, 3),
    }


if __name__ == "__main__":
    # Sanity check against our three planted ground-truth pairs.
    pairs = [
        ("abc123", "123_abc", "EASY pair (same person) — expect HIGH"),
        ("nightowl_88", "darkraven", "MEDIUM pair (same person) — expect LOW (username alone shouldn't catch this)"),
        ("john123", "john124", "DECOY pair (different people) — expect misleadingly HIGH"),
    ]
    for a, b, note in pairs:
        result = username_similarity(a, b)
        print(note)
        print(" ", result)
        print()