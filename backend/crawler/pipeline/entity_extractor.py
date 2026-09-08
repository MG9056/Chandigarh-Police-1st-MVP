import logging
import os
import re
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

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
        \+\d{1,3}(?:[\s-]?\d){10}
        |
        \(\d{3}\)[\s-]?\d{3}[\s-]?\d{4}
    )
    (?!\d)
    """,
    re.VERBOSE,
)


class EntityExtractor:
    """
    Extracts candidate entities from cleaned text.

    The NER engine can be switched between:
        - spaCy
        - GLiNER

    Set the ENTITY_EXTRACTOR environment variable to:
        ENTITY_EXTRACTOR=spacy
    or:
        ENTITY_EXTRACTOR=gliner

    If ENTITY_EXTRACTOR is not set, spaCy is used by default.

    Regex provides deterministic extraction for:
        BITCOIN_ADDRESS
        ETHEREUM_ADDRESS
        PHONE_NUMBER

    GLiNER confidence scores are preserved because they are produced
    directly by the NER model. They are NOT treated as final
    investigation confidence. Final contextual relevance/confidence
    is assigned later by the LLM.

    IMPORTANT:
    The selected NER model is loaded lazily on the first call to
    extract() and then reused for subsequent records. This prevents
    large NER models from consuming RAM during application startup.
    """

    # ------------------------------------------------------------------
    # GLiNER labels
    # ------------------------------------------------------------------

    GLINER_LABELS = [
        "person",
        "organization",
        "drug",
        "drug quantity",
        "drug price",
        "vendor",
        "marketplace",
        "messaging platform",
        "username",
        "cryptocurrency",
        "location",
        "law enforcement agency",
        "email address",
    ]

    # Only send reasonably sized text to the NER model.
    MAX_TEXT_LENGTH = 10000

    # Minimum GLiNER confidence accepted as a candidate.
    GLINER_THRESHOLD = 0.5

    def __init__(self):
        # Model is intentionally NOT loaded here.
        # This keeps EntityExtractor lightweight during imports/startup.
        self.model = None

        # Default to spaCy so the project works without GLiNER.
        self.extractor_type = os.getenv(
            "ENTITY_EXTRACTOR",
            "spacy",
        ).lower()

        # Treat any value other than "gliner" as spaCy.
        if self.extractor_type != "gliner":
            self.extractor_type = "spacy"

        logger.info(
            "EntityExtractor initialized with engine '%s'. "
            "Model loading is deferred until first extraction.",
            self.extractor_type,
        )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_spacy(self):
        """
        Load spaCy NER model lazily.
        """

        # Prevent repeated loading if multiple calls race through here.
        if self.model is not None:
            return

        try:
            import spacy

            logger.info(
                "Loading spaCy entity extractor lazily..."
            )

            self.model = spacy.load(
                "en_core_web_sm"
            )

            logger.info(
                "spaCy entity extractor loaded successfully."
            )

        except Exception as e:
            logger.error(
                "spaCy model could not be loaded: %s. "
                "Regex extraction will still be available.",
                e,
                exc_info=True,
            )

            self.model = None

    def _load_gliner(self):
        """
        Load GLiNER NER model lazily.
        """

        # Prevent repeated loading if model is already available.
        if self.model is not None:
            return

        try:
            from gliner import GLiNER

            logger.info(
                "Loading GLiNER model "
                "urchade/gliner_medium-v2.1 lazily..."
            )

            self.model = GLiNER.from_pretrained(
                "urchade/gliner_medium-v2.1"
            )

            logger.info(
                "GLiNER model loaded successfully."
            )

        except Exception as e:
            logger.error(
                "GLiNER model could not be loaded: %s. "
                "Regex extraction will still be available.",
                e,
                exc_info=True,
            )

            self.model = None

    def _ensure_model_loaded(self):
        """
        Lazily load the configured NER model.

        This method is called only when semantic NER extraction is
        actually requested.
        """

        if self.model is not None:
            return

        if self.extractor_type == "gliner":
            self._load_gliner()
        else:
            self._load_spacy()

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

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
        decimal/numeric content than phone numbers.
        """

        if "." in phone:
            return True

        before = text[max(0, start - 2):start]
        after = text[end:end + 2]

        if (
            before.endswith(".")
            and len(before) >= 2
            and before[-2].isdigit()
        ):
            return True

        if (
            after.startswith(".")
            and len(after) >= 2
            and after[1].isdigit()
        ):
            return True

        return False

    @staticmethod
    def _clean_entity_text(text: str) -> str:
        """
        Clean whitespace and surrounding punctuation from a NER
        entity without changing its actual content.
        """

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        text = text.strip(
            " \t\r\n.,;:!?()[]{}<>\"'`"
        )

        return text

    @staticmethod
    def _candidate(
        entity_type: str,
        value: str,
        source: str,
        confidence: float | None = None,
    ) -> Dict[str, Any]:
        """
        Create a machine-extracted candidate.
        """

        return {
            "type": entity_type,
            "value": value,
            "confidence": confidence,
            "confidence_source": source,
        }

    @staticmethod
    def _dedupe_key(
        entity_type: str,
        value: str,
        case_sensitive: bool,
    ) -> tuple:
        """
        Build a deduplication key.

        Bitcoin addresses are case-sensitive because Base58 casing
        changes the actual address.

        Other entity values are treated case-insensitively.
        """

        return (
            entity_type.casefold(),
            value if case_sensitive else value.casefold(),
        )

    @classmethod
    def _deduplicate_candidates(
        cls,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate candidates while tracking mention counts.
        """

        seen: Dict[tuple, Dict[str, Any]] = {}
        order: List[tuple] = []

        for candidate in candidates:
            value = str(
                candidate.get("value", "")
            ).strip()

            entity_type = str(
                candidate.get("type", "")
            ).strip()

            if not value or not entity_type:
                continue

            case_sensitive = (
                entity_type == "BITCOIN_ADDRESS"
            )

            key = cls._dedupe_key(
                entity_type,
                value,
                case_sensitive,
            )

            if key not in seen:
                seen[key] = dict(candidate)
                seen[key]["mention_count"] = 1
                order.append(key)

            else:
                seen[key]["mention_count"] += 1

                # Keep the highest model confidence if the same
                # entity was detected multiple times.
                existing_confidence = seen[key].get(
                    "confidence"
                )

                new_confidence = candidate.get(
                    "confidence"
                )

                if (
                    new_confidence is not None
                    and (
                        existing_confidence is None
                        or new_confidence > existing_confidence
                    )
                ):
                    seen[key]["confidence"] = new_confidence

        return [
            seen[key]
            for key in order
        ]

    # ------------------------------------------------------------------
    # spaCy extraction
    # ------------------------------------------------------------------

    def _extract_with_spacy(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract general entities using spaCy.
        """

        if not text or not text.strip():
            return []

        # Model should already be loaded by extract(), but keeping this
        # guard makes the method safe if called directly.
        if not self.model:
            return []

        candidates: List[Dict[str, Any]] = []

        try:
            model_text = text[:self.MAX_TEXT_LENGTH]

            doc = self.model(model_text)

            for entity in doc.ents:
                value = self._clean_entity_text(
                    entity.text
                )

                label = str(
                    entity.label_
                ).strip()

                if not value or not label:
                    continue

                candidates.append(
                    self._candidate(
                        entity_type=label,
                        value=value,
                        source="spacy_ner",
                        confidence=None,
                    )
                )

        except Exception as e:
            logger.error(
                "Error in spaCy NER processing: %s",
                e,
                exc_info=True,
            )

        return candidates

    # ------------------------------------------------------------------
    # GLiNER extraction
    # ------------------------------------------------------------------

    def _extract_with_gliner(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract domain-specific entities using GLiNER.
        """

        if not text or not text.strip():
            return []

        # Model should already be loaded by extract(), but keeping this
        # guard makes the method safe if called directly.
        if not self.model:
            return []

        candidates: List[Dict[str, Any]] = []

        try:
            model_text = text[:self.MAX_TEXT_LENGTH]

            entities = self.model.predict_entities(
                model_text,
                self.GLINER_LABELS,
                threshold=self.GLINER_THRESHOLD,
            )

            for entity in entities:
                value = self._clean_entity_text(
                    str(entity.get("text", ""))
                )

                label = str(
                    entity.get("label", "")
                ).strip()

                score = entity.get("score")

                if not value or not label:
                    continue

                try:
                    confidence = (
                        float(score)
                        if score is not None
                        else None
                    )
                except (TypeError, ValueError):
                    confidence = None

                candidates.append(
                    self._candidate(
                        entity_type=self._normalise_gliner_label(
                            label
                        ),
                        value=value,
                        source="gliner_ner",
                        confidence=confidence,
                    )
                )

        except Exception as e:
            logger.error(
                "Error in GLiNER NER processing: %s",
                e,
                exc_info=True,
            )

        return candidates

    @staticmethod
    def _normalise_gliner_label(label: str) -> str:
        """
        Convert GLiNER labels into stable pipeline entity types.

        Keeping these as readable uppercase identifiers makes the
        output consistent with the existing regex-based candidates.
        """

        label_mapping = {
            "person": "PERSON",
            "organization": "ORGANIZATION",
            "drug": "DRUG",
            "drug quantity": "DRUG_QUANTITY",
            "drug price": "DRUG_PRICE",
            "vendor": "VENDOR",
            "marketplace": "MARKETPLACE",
            "messaging platform": "MESSAGING_PLATFORM",
            "username": "USERNAME",
            "cryptocurrency": "CRYPTOCURRENCY",
            "cryptocurrency wallet": "CRYPTOCURRENCY_WALLET",
            "location": "LOCATION",
            "law enforcement agency": "LAW_ENFORCEMENT_AGENCY",
            "email address": "EMAIL_ADDRESS",
            "phone number": "PHONE_NUMBER",
        }

        return label_mapping.get(
            label.casefold(),
            label.upper().replace(" ", "_"),
        )

    # ------------------------------------------------------------------
    # Main extraction
    # ------------------------------------------------------------------

    def extract(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract all candidate entities from text.

        The selected NER engine handles semantic entities.

        Regex handles deterministic entities such as wallet addresses
        and phone numbers.

        The NER model is loaded lazily here on the first extraction
        request, not during EntityExtractor construction.
        """

        if not text or not text.strip():
            return []

        candidates: List[Dict[str, Any]] = []

        # --------------------------------------------------------------
        # 1. Lazy-load NER model only when extraction is actually used
        # --------------------------------------------------------------

        self._ensure_model_loaded()

        if self.extractor_type == "gliner":
            candidates.extend(
                self._extract_with_gliner(text)
            )
        else:
            candidates.extend(
                self._extract_with_spacy(text)
            )

        # --------------------------------------------------------------
        # 2. Bitcoin addresses
        # --------------------------------------------------------------

        for btc in BTC_REGEX.findall(text):
            candidates.append(
                self._candidate(
                    entity_type="BITCOIN_ADDRESS",
                    value=btc,
                    source="bitcoin_regex",
                )
            )

        # --------------------------------------------------------------
        # 3. Ethereum addresses
        # --------------------------------------------------------------

        for eth in ETH_REGEX.findall(text):
            candidates.append(
                self._candidate(
                    entity_type="ETHEREUM_ADDRESS",
                    value=eth,
                    source="ethereum_regex",
                )
            )

        # --------------------------------------------------------------
        # 4. Phone numbers
        # --------------------------------------------------------------

        seen_phone_keys = set()

        for match in PHONE_REGEX.finditer(text):
            phone = self._normalise_phone(
                match.group(0)
            )

            if not phone:
                continue

            phone_key = re.sub(
                r"\D",
                "",
                phone,
            )

            if phone_key in seen_phone_keys:
                continue

            digit_count = self._phone_digit_count(
                phone
            )

            if digit_count < 10 or digit_count > 15:
                continue

            if self._looks_like_decimal_or_numeric_sequence(
                phone,
                text,
                match.start(),
                match.end(),
            ):
                continue

            seen_phone_keys.add(phone_key)

            candidates.append(
                self._candidate(
                    entity_type="PHONE_NUMBER",
                    value=phone,
                    source="phone_regex",
                )
            )

        # --------------------------------------------------------------
        # 5. Deduplicate
        # --------------------------------------------------------------

        candidates = self._deduplicate_candidates(
            candidates
        )

        logger.debug(
            "Extracted %d candidate entities using %s.",
            len(candidates),
            self.extractor_type,
        )

        return candidates