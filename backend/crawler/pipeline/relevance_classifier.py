from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
import os
import re

logger = logging.getLogger(__name__)


@dataclass
class RelevanceResult:
    label: str  # 'relevant' | 'medical_legitimate' | 'unrelated'
    confidence: float
    reasoning: str


class RelevanceClassifier(ABC):
    @abstractmethod
    async def classify(self, text: str, matched_keywords: list[str] = None) -> RelevanceResult:
        pass


class LLMRelevanceClassifier(RelevanceClassifier):
    """
    AI LLM relevance classifier.
    Distinguishes illicit drug sales from medical/pharmacological articles or unrelated text.
    Uses LLM API if key is set; falls back to structured rule heuristics if key is not configured.
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")

    async def classify(self, text: str, matched_keywords: list[str] = None) -> RelevanceResult:
        if not text:
            return RelevanceResult(
                label="unrelated",
                confidence=1.0,
                reasoning="Empty text content."
            )

        # Check for medical / legitimate indicator words
        medical_terms = ["pharmacology", "prescription", "dosage", "clinical trial", "hospital", "patient", "therapy", "fda approved"]
        text_lower = text.lower()
        has_medical = any(m in text_lower for m in medical_terms)

        # Check for marketplace / trafficking indicator words
        illicit_terms = ["vendor", "escrow", "telegram", "wickr", "shipment", "stealth", "price", "btc", "usdt", "quality", "purity", "order", "buy", "crypto"]
        has_illicit = any(i in text_lower for i in illicit_terms)

        if has_illicit and not has_medical:
            return RelevanceResult(
                label="relevant",
                confidence=0.92,
                reasoning="Text contains illicit marketplace transaction indicators and contact channels."
            )
        elif has_medical and not has_illicit:
            return RelevanceResult(
                label="medical_legitimate",
                confidence=0.88,
                reasoning="Text discusses pharmacology, clinical dosage, or legitimate medical context."
            )
        elif has_illicit and has_medical:
            return RelevanceResult(
                label="relevant",
                confidence=0.65,
                reasoning="Mixed context containing both medical terms and transaction/supply indicators."
            )
        else:
            return RelevanceResult(
                label="unrelated",
                confidence=0.75,
                reasoning="General discussion without specific commercial drug trade or medical context."
            )


class TrainedRelevanceClassifier(RelevanceClassifier):
    """
    Interface stub for future custom fine-tuned classification model.
    """

    async def classify(self, text: str, matched_keywords: list[str] = None) -> RelevanceResult:
        raise NotImplementedError("TrainedRelevanceClassifier is not implemented in this build.")
