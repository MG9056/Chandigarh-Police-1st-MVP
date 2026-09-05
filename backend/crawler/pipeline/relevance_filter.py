import re
from typing import List, Tuple


class KeywordMatcher:
    """
    Cheap, fast first-pass keyword pre-filter.
    Filters content before invoking expensive AI LLM classification steps.
    """

    @staticmethod
    def match(text: str, active_keywords: List[str]) -> Tuple[List[str], bool]:
        if not text or not active_keywords:
            return [], False

        text_lower = text.lower()
        matched = []

        for kw in active_keywords:
            if not kw or not kw.strip():
                continue
            kw_clean = kw.strip().lower()
            # Simple substring / word boundary match
            pattern = re.compile(rf"\b{re.escape(kw_clean)}\b", re.IGNORECASE)
            if pattern.search(text_lower) or kw_clean in text_lower:
                matched.append(kw)

        is_passed = len(matched) > 0
        return matched, is_passed
