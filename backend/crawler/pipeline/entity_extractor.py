import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Regex patterns for wallet addresses & phone numbers
BTC_REGEX = re.compile(r"\b(1[a-km-zA-HJ-NP-Z1-9]{25,34}|3[a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b")
ETH_REGEX = re.compile(r"\b(0x[a-fA-F0-9]{40})\b")

PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


class EntityExtractor:
    """
    Extracts candidate entities (names, locations, orgs via spaCy NER, and wallet addresses / phone numbers via regex).
    All outputs are explicitly confidence-tagged candidate objects.
    """

    def __init__(self):
        self.nlp = None
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            logger.info(f"spaCy en_core_web_sm model not loaded ({e}); fallback regex extraction will be used.")

    def extract(self, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []

        candidates = []

        # 1. spaCy NER
        if self.nlp:
            try:
                doc = self.nlp(text[:10000])  # Cap at 10,000 chars for efficiency
                for ent in doc.ents:
                    if ent.label_ in ("PERSON", "GPE", "ORG", "LOC"):
                        candidates.append({
                            "type": ent.label_,
                            "value": ent.text.strip(),
                            "confidence": 0.85,
                        })
            except Exception as e:
                logger.error(f"Error in spaCy NER processing: {e}")

        # 2. Bitcoin Wallet Addresses Regex
        btc_matches = BTC_REGEX.findall(text)
        for btc in set(btc_matches):
            candidates.append({
                "type": "BITCOIN_ADDRESS",
                "value": btc,
                "confidence": 0.98,
            })

        # 3. Ethereum Wallet Addresses Regex
        eth_matches = ETH_REGEX.findall(text)
        for eth in set(eth_matches):
            candidates.append({
                "type": "ETHEREUM_ADDRESS",
                "value": eth,
                "confidence": 0.98,
            })

        # 4. Phone Numbers Regex
        phone_matches = PHONE_REGEX.findall(text)
        for phone in set(phone_matches):
            if len(phone.strip()) >= 10:
                candidates.append({
                    "type": "PHONE_NUMBER",
                    "value": phone.strip(),
                    "confidence": 0.80,
                })

        return candidates
