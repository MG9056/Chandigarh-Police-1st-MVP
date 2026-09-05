from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import logging
import os
from typing import Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


@dataclass
class RelevanceResult:
    label: str
    confidence: float
    reasoning: str
    indicators: list[str]
    structured_intelligence: dict


class RelevanceClassifier(ABC):
    @abstractmethod
    async def classify(
        self,
        text: str,
        matched_keywords: list[str] = None,
        extracted_candidates: list[dict] = None,
    ) -> RelevanceResult:
        pass


class LLMRelevanceClassifier(RelevanceClassifier):
    """
    Gemini-powered relevance and intelligence classifier.

    Input:
        - cleaned source text
        - matched investigation keywords
        - machine-extracted candidates from spaCy/regex

    Output:
        - relevance label
        - model-generated confidence
        - reasoning
        - indicators
        - structured entities
        - relationships

    If the LLM is unavailable, a conservative rule-based fallback
    keeps the crawler operational.
    """

    SYSTEM_INSTRUCTION = """
You are an intelligence analyst operating inside a law-enforcement
OSINT pipeline.

Your task is to analyze supplied source content and determine whether
it is relevant to suspected illicit drug trade activity.

You must distinguish illicit activity from legitimate medical,
pharmacological, scientific, educational, regulatory, and clinical
discussion.

Allowed classification labels:

1. "relevant"
Use when the content provides meaningful evidence or context related
to illicit drug sales, trafficking, distribution, procurement,
suspicious supply activity, transaction activity, illicit marketplace
activity, or associated contact/payment channels.

2. "medical_legitimate"
Use when the content is primarily legitimate medical,
pharmacological, clinical, educational, regulatory, or scientific
discussion without meaningful evidence of illicit drug commerce.

3. "unrelated"
Use when the content does not meaningfully fit either category.

Important rules:

- Matched keywords are hints, not proof.
- Do not classify something as illicit solely because a drug name
  appears.
- Use the surrounding context.
- Do not invent facts.
- Do not invent entities.
- Do not invent relationships.
- Validate machine-extracted candidates against the source content.
- Only include entities that are actually supported by the content.
- Only include relationships that are actually supported by the
  content.
- Confidence must reflect how strongly the supplied content supports
  the classification.
- Return only JSON matching the supplied schema.
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = (
            api_key
            if api_key is not None
            else os.environ.get("LLM_API_KEY", "")
        )

        self.model = (
            model
            or os.environ.get(
                "LLM_MODEL",
                "gemini-3.6-flash",
            )
        )

        self.client = None

        if self.api_key:
            self.client = genai.Client(
                api_key=self.api_key
            )

    async def classify(
        self,
        text: str,
        matched_keywords: list[str] = None,
        extracted_candidates: list[dict] = None,
    ) -> RelevanceResult:

        if not text:
            return RelevanceResult(
                label="unrelated",
                confidence=1.0,
                reasoning="Empty text content.",
                indicators=[],
                structured_intelligence={
                    "entities": [],
                    "relationships": [],
                },
            )

        matched_keywords = matched_keywords or []
        extracted_candidates = extracted_candidates or []

        if not self.client:
            logger.warning(
                "LLM_API_KEY is not configured. "
                "Using conservative fallback classification."
            )

            return self._fallback_classify(
                text,
                matched_keywords,
            )

        prompt = self._build_prompt(
            text=text,
            matched_keywords=matched_keywords,
            extracted_candidates=extracted_candidates,
        )

        schema = {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "enum": [
                        "relevant",
                        "medical_legitimate",
                        "unrelated",
                    ],
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "reasoning": {
                    "type": "string",
                },
                "indicators": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                            },
                            "value": {
                                "type": "string",
                            },
                            "role": {
                                "type": "string",
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                        },
                        "required": [
                            "type",
                            "value",
                            "role",
                            "confidence",
                        ],
                    },
                },
                "relationships": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject": {
                                "type": "string",
                            },
                            "relation": {
                                "type": "string",
                            },
                            "object": {
                                "type": "string",
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                        },
                        "required": [
                            "subject",
                            "relation",
                            "object",
                            "confidence",
                        ],
                    },
                },
            },
            "required": [
                "label",
                "confidence",
                "reasoning",
                "indicators",
                "entities",
                "relationships",
            ],
        }

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.1,
                    max_output_tokens=800,
                ),
            )

            response_text = response.text

            if not response_text:
                raise ValueError(
                    "Gemini returned an empty response."
                )

            parsed = json.loads(response_text)

            label = parsed.get("label")
            confidence = parsed.get("confidence")
            reasoning = parsed.get("reasoning")
            indicators = parsed.get("indicators", [])
            entities = parsed.get("entities", [])
            relationships = parsed.get(
                "relationships",
                [],
            )

            if label not in {
                "relevant",
                "medical_legitimate",
                "unrelated",
            }:
                raise ValueError(
                    f"Invalid classification label: {label}"
                )

            confidence = float(confidence)

            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    f"Invalid confidence value: {confidence}"
                )

            if not isinstance(reasoning, str):
                raise ValueError(
                    "Gemini reasoning must be a string."
                )

            if not isinstance(indicators, list):
                indicators = []

            if not isinstance(entities, list):
                entities = []

            if not isinstance(relationships, list):
                relationships = []

            validated_entities = []

            for entity in entities:
                if not isinstance(entity, dict):
                    continue

                entity_type = entity.get("type")
                entity_value = entity.get("value")
                entity_role = entity.get("role")
                entity_confidence = entity.get("confidence")

                if not all([
                    isinstance(entity_type, str),
                    isinstance(entity_value, str),
                    isinstance(entity_role, str),
                ]):
                    continue

                try:
                    entity_confidence = float(
                        entity_confidence
                    )
                except (TypeError, ValueError):
                    continue

                if not 0.0 <= entity_confidence <= 1.0:
                    continue

                validated_entities.append({
                    "type": entity_type,
                    "value": entity_value,
                    "role": entity_role,
                    "confidence": entity_confidence,
                })

            validated_relationships = []

            for relationship in relationships:
                if not isinstance(relationship, dict):
                    continue

                subject = relationship.get("subject")
                relation = relationship.get("relation")
                object_value = relationship.get("object")
                relationship_confidence = relationship.get(
                    "confidence"
                )

                if not all([
                    isinstance(subject, str),
                    isinstance(relation, str),
                    isinstance(object_value, str),
                ]):
                    continue

                try:
                    relationship_confidence = float(
                        relationship_confidence
                    )
                except (TypeError, ValueError):
                    continue

                if not 0.0 <= relationship_confidence <= 1.0:
                    continue

                validated_relationships.append({
                    "subject": subject,
                    "relation": relation,
                    "object": object_value,
                    "confidence": relationship_confidence,
                })

            structured_intelligence = {
                "entities": validated_entities,
                "relationships": validated_relationships,
            }

            return RelevanceResult(
                label=label,
                confidence=confidence,
                reasoning=reasoning,
                indicators=[
                    str(item)
                    for item in indicators
                ],
                structured_intelligence=structured_intelligence,
            )

        except Exception as exc:
            logger.error(f"Gemini relevance classification failed: {exc}", exc_info=True)
            return self._fallback_classify(text, matched_keywords)
    
    @staticmethod
    def _build_prompt(
        text: str,
        matched_keywords: list[str],
        extracted_candidates: list[dict],
    ) -> str:
        keywords_text = (
            ", ".join(matched_keywords)
            if matched_keywords
            else "None"
        )

        candidates_text = json.dumps(
            extracted_candidates,
            ensure_ascii=False,
            indent=2,
        )

        return f"""
Analyze the following cleaned source content.

Matched investigation keywords:
{keywords_text}

Machine-extracted candidate entities from spaCy/regex:
----------------
{candidates_text}
----------------

Source content:
----------------
{text[:15000]}
----------------

Tasks:

1. Classify the source as:
   - relevant
   - medical_legitimate
   - unrelated

2. Evaluate the machine-extracted candidates against the source
   context. Keep only candidates that are actually supported.

3. Identify important entities that are supported by the source.

4. Identify meaningful relationships between supported entities.

5. Identify important intelligence indicators.

Return JSON with:
- label
- confidence
- reasoning
- indicators
- entities
- relationships

Entity format:
{{
  "type": "PERSON | ORGANIZATION | LOCATION | DRUG | PLATFORM | PHONE_NUMBER | BITCOIN_ADDRESS | ETHEREUM_ADDRESS | OTHER",
  "value": "entity value",
  "role": "role in the content",
  "confidence": 0.0
}}

Relationship format:
{{
  "subject": "entity",
  "relation": "relationship",
  "object": "entity",
  "confidence": 0.0
}}

Do not add information that is not supported by the source.
"""

    @staticmethod
    def _fallback_classify(
        text: str,
        matched_keywords: list[str],
    ) -> RelevanceResult:
        """
        Conservative fallback if Gemini is unavailable.

        This is only a failure fallback. The primary classifier is
        Gemini.
        """

        if not text:
            return RelevanceResult(
                label="unrelated",
                confidence=1.0,
                reasoning="Empty text content.",
                indicators=[],
                structured_intelligence={
                    "entities": [],
                    "relationships": [],
                },
            )

        text_lower = text.lower()

        medical_terms = [
            "pharmacology",
            "prescription",
            "dosage",
            "clinical trial",
            "hospital",
            "patient",
            "therapy",
            "fda approved",
        ]

        illicit_terms = [
            "vendor",
            "escrow",
            "telegram",
            "wickr",
            "shipment",
            "stealth",
            "price",
            "btc",
            "usdt",
            "quality",
            "purity",
            "order",
            "buy",
            "crypto",
        ]

        medical_matches = [
            term
            for term in medical_terms
            if term in text_lower
        ]

        illicit_matches = [
            term
            for term in illicit_terms
            if term in text_lower
        ]

        if illicit_matches and not medical_matches:
            return RelevanceResult(
                label="relevant",
                confidence=0.60,
                reasoning=(
                    "Gemini unavailable; fallback detected "
                    "illicit-activity indicators."
                ),
                indicators=illicit_matches,
                structured_intelligence={
                    "entities": [],
                    "relationships": [],
                },
            )

        if medical_matches and not illicit_matches:
            return RelevanceResult(
                label="medical_legitimate",
                confidence=0.60,
                reasoning=(
                    "Gemini unavailable; fallback detected "
                    "medical-context indicators."
                ),
                indicators=medical_matches,
                structured_intelligence={
                    "entities": [],
                    "relationships": [],
                },
            )

        return RelevanceResult(
            label="unrelated",
            confidence=0.50,
            reasoning=(
                "Gemini unavailable and fallback could not "
                "establish strong relevance."
            ),
            indicators=(
                medical_matches + illicit_matches
            ),
            structured_intelligence={
                "entities": [],
                "relationships": [],
            },
        )


class TrainedRelevanceClassifier(RelevanceClassifier):
    """
    Interface stub for future custom fine-tuned classification model.
    """

    async def classify(
        self,
        text: str,
        matched_keywords: list[str] = None,
        extracted_candidates: list[dict] = None,
    ) -> RelevanceResult:
        raise NotImplementedError(
            "TrainedRelevanceClassifier is not implemented "
            "in this build."
        )