import logging
import re

logger = logging.getLogger(__name__)


class LanguageDetector:
    """
    Detects natural language of text (English, Hindi, Punjabi, etc.).
    Uses langdetect if available, with Devanagari/Gurmukhi Unicode range heuristic fallbacks.
    """

    @staticmethod
    def detect(text: str) -> str:
        if not text or not text.strip():
            return "unknown"

        # Check for Gurmukhi script (Punjabi)
        if re.search(r"[\u0A00-\u0A7F]", text):
            return "pa"

        # Check for Devanagari script (Hindi)
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"

        try:
            import langdetect
            lang = langdetect.detect(text)
            return lang
        except Exception:
            return "en"
