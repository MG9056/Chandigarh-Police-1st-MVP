import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Wallet address patterns
# ------------------------------------------------------------------

BTC_REGEX = re.compile(
    r"\b(?:"
    r"1[a-km-zA-HJ-NP-Z1-9]{25,34}"
    r"|"
    r"3[a-km-zA-HJ-NP-Z1-9]{25,34}"
    r"|"
    r"bc1[a-z0-9]{39,59}"
    r")\b"
)

ETH_REGEX = re.compile(
    r"\b0x[a-fA-F0-9]{40}\b"
)


# ------------------------------------------------------------------
# Phone number pattern
# ------------------------------------------------------------------

PHONE_REGEX = re.compile(
    r"""
    (?<![\d.])
    (?:
        \+\d{1,3}[\s-]?
    )?
    (?:\(\d{2,4}\)[\s-]?)?
    \d{3,4}[\s-]?\d{3,4}
    (?![\d.])
    """,
    re.VERBOSE,
)


class EntityExtractor:
    """
    Extracts candidate entities from cleaned text.

    spaCy provides:
        PERSON
        GPE
        ORG
        LOC

    Regex provides:
        BITCOIN_ADDRESS
        ETHEREUM_ADDRESS
        PHONE_NUMBER

    The extractor does NOT assign fake probability-style confidence
    values. It produces candidates and records how each candidate
    was detected.

    Final contextual confidence is assigned later by the LLM.
    """

    def __init__(self):
        self.nlp = None

        try:
            import spacy

            self.nlp = spacy.load("en_core_web_sm")

        except Exception as e:
            logger.info(
                "spaCy en_core_web_sm model not loaded "
                f"({e}); fallback regex extraction will be used."
            )

    @staticmethod
    def _normalise_phone(phone: str) -> str:
        """
        Keep the original formatting while normalising whitespace.
        """
        return re.sub(r"\s+", " ", phone.strip())

    @staticmethod
    def _phone_digit_count(phone: str) -> int:
        """
        Count numeric digits only.
        """
        return len(re.sub(r"\D", "", phone))

    @staticmethod
    def _looks_like_decimal_or_numeric_sequence(
        phone: str,
        text: str,
        start: int,
        end: int,
    ) -> bool:
        """
        Reject candidates that are more likely to be ordinary
        numeric/decimal content than phone numbers.
        """

        if "." in phone:
            return True

        before = text[max(0, start - 2):start]
        after = text[end:end + 2]

        if "." in before or "." in after:
            return True

        return False

    @staticmethod
    def _candidate(
        entity_type: str,
        value: str,
        source: str,
    ) -> Dict[str, Any]:
        """
        Create a machine-extracted candidate.

        Confidence is intentionally left unset because this extractor
        does not produce calibrated probabilities.
        """

        return {
            "type": entity_type,
            "value": value,
            "confidence": None,
            "confidence_source": source,
        }

    def extract(self, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []

        candidates: List[Dict[str, Any]] = []

        # ----------------------------------------------------------
        # 1. spaCy NER
        # ----------------------------------------------------------
        if self.nlp:
            try:
                doc = self.nlp(text[:10000])

                for ent in doc.ents:
                    if ent.label_ in (
                        "PERSON",
                        "GPE",
                        "ORG",
                        "LOC",
                    ):
                        value = ent.text.strip()

                        if not value:
                            continue

                        candidates.append(
                            self._candidate(
                                entity_type=ent.label_,
                                value=value,
                                source="spacy_ner",
                            )
                        )

            except Exception as e:
                logger.error(
                    f"Error in spaCy NER processing: {e}"
                )

        # ----------------------------------------------------------
        # 2. Bitcoin addresses
        # ----------------------------------------------------------
        seen_btc = set()

        for btc in BTC_REGEX.findall(text):
            if btc in seen_btc:
                continue

            seen_btc.add(btc)

            candidates.append(
                self._candidate(
                    entity_type="BITCOIN_ADDRESS",
                    value=btc,
                    source="bitcoin_regex",
                )
            )

        # ----------------------------------------------------------
        # 3. Ethereum addresses
        # ----------------------------------------------------------
        seen_eth = set()

        for eth in ETH_REGEX.findall(text):
            if eth in seen_eth:
                continue

            seen_eth.add(eth)

            candidates.append(
                self._candidate(
                    entity_type="ETHEREUM_ADDRESS",
                    value=eth,
                    source="ethereum_regex",
                )
            )

        # ----------------------------------------------------------
        # 4. Phone numbers
        # ----------------------------------------------------------
        seen_phones = set()

        for match in PHONE_REGEX.finditer(text):
            phone = self._normalise_phone(
                match.group(0)
            )

            if not phone:
                continue

            if phone in seen_phones:
                continue

            digit_count = self._phone_digit_count(phone)

            if digit_count < 10 or digit_count > 15:
                continue

            if self._looks_like_decimal_or_numeric_sequence(
                phone,
                text,
                match.start(),
                match.end(),
            ):
                continue

            seen_phones.add(phone)

            candidates.append(
                self._candidate(
                    entity_type="PHONE_NUMBER",
                    value=phone,
                    source="phone_regex",
                )
            )

        return candidates