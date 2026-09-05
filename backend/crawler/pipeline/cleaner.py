import logging
import re

try:
    import trafilatura
except ImportError:
    trafilatura = None

logger = logging.getLogger(__name__)



class ContentCleaner:
    """
    Strips navigation, footers, scripts, and ads from HTML, returning main readable body text.
    Uses trafilatura with regex/BeautifulSoup fallback.
    """

    @staticmethod
    def clean(raw_html_or_text: str | None) -> str:
        if not raw_html_or_text:
            return ""

        # Try trafilatura main content extraction
        if trafilatura is not None:
            try:
                extracted = trafilatura.extract(
                    raw_html_or_text,
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False,
                )
                if extracted and extracted.strip():
                    return extracted.strip()
            except Exception as e:
                logger.debug(f"trafilatura extraction fallback triggered: {e}")


        # Fallback simple regex HTML tag stripping if trafilatura returns None
        text = re.sub(r"<script.*?>.*?</script>", "", raw_html_or_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
