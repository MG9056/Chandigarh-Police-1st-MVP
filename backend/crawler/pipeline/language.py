import logging
import re

logger = logging.getLogger(__name__)

try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
except ImportError:
    detect = None


class LanguageDetector:
    """
    Detects the language of scraped text.

    Uses Unicode script detection for Punjabi and Hindi first,
    then falls back to langdetect for other languages.
    """

    @staticmethod
    def detect(text: str) -> str:
        if not text or not text.strip():
            return "unknown"

        # Punjabi / Gurmukhi
        if re.search(r"[\u0A00-\u0A7F]", text):
            return "pa"

        # Hindi / Devanagari
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"

        # Other languages
        if detect is not None:
            try:
                return detect(text)
            except Exception:
                logger.warning("Could not detect language")

        return "unknown"