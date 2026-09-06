"""Read-only semantic search index for existing intelligence records.

The index is deliberately kept outside the application database. It stores
source identifiers and embeddings only; the database remains authoritative.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_INDEX_PATH = Path(__file__).with_name(".semantic_index.json")


@dataclass
class SemanticDocument:
    source_type: str
    source_id: str
    text: str
    case_id: Optional[str] = None


class LocalEmbeddingProvider:
    """Local multilingual embeddings; no LLM API or API key is required."""

    _models = {}

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("SEMANTIC_SEARCH_MODEL", DEFAULT_MODEL)
        self._model = None

    @property
    def available(self) -> bool:
        return True

    def _get_model(self):
        if self._model is None:
            if self.model not in self._models:
                from sentence_transformers import SentenceTransformer

                self._models[self.model] = SentenceTransformer(self.model)
            self._model = self._models[self.model]
        return self._model

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        values = [text[:12000] for text in texts]
        if not values:
            return []
        embeddings = self._get_model().encode(values, normalize_embeddings=True)
        return embeddings.tolist()


def _normalise_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def _document_text(*values) -> str:
    return " ".join(part.strip() for part in (_normalise_text(value) for value in values) if part.strip())


def build_documents(db) -> list[SemanticDocument]:
    """Create read-only documents from current database rows."""
    from crawler.models.raw_record import RawRecord
    from models import CryptoWallet, DarknetListing, Suspect, TelegramMessage

    documents = []
    for record in db.query(Suspect).all():
        documents.append(SemanticDocument(
            "suspect", str(record.id),
            _document_text(record.primary_alias, record.aliases_json, record.telegram_handle,
                           record.last_known_location, record.platform_mentions,
                           record.enrichment_summary, record.notes),
        ))
    for record in db.query(CryptoWallet).all():
        documents.append(SemanticDocument(
            "wallet", str(record.id),
            _document_text(record.address, record.currency, record.risk_level),
        ))
    for record in db.query(DarknetListing).all():
        documents.append(SemanticDocument(
            "listing", str(record.id),
            _document_text(record.title, record.vendor_alias, record.platform,
                           record.drug_category, record.location, record.description),
        ))
    for record in db.query(TelegramMessage).all():
        documents.append(SemanticDocument(
            "telegram", str(record.id),
            _document_text(record.sender_handle, record.message_text,
                           record.detected_wallets_json, record.detected_keywords_json),
        ))
    for record in db.query(RawRecord).all():
        documents.append(SemanticDocument(
            "raw_record", str(record.id),
            _document_text(record.url, record.cleaned_text, record.raw_text,
                           record.matched_keywords, record.relevance_reasoning,
                           record.extracted_candidates),
            record.case_id,
        ))
    return [document for document in documents if document.text]


class SemanticIndex:
    def __init__(self, path: Optional[str | Path] = None, provider=None):
        self.path = Path(path or os.getenv("SEMANTIC_SEARCH_INDEX_PATH", DEFAULT_INDEX_PATH))
        self.provider = provider or LocalEmbeddingProvider()

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload.get("documents", [])
        except (OSError, json.JSONDecodeError):
            return []

    def rebuild(self, db) -> int:
        documents = build_documents(db)
        vectors = self.provider.embed(document.text for document in documents)
        indexed = []
        for document, vector in zip(documents, vectors):
            indexed.append({
                "source_type": document.source_type,
                "source_id": document.source_id,
                "case_id": document.case_id,
                "content_hash": hashlib.sha256(document.text.encode("utf-8")).hexdigest(),
                "vector": vector,
            })
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"model": self.provider.model, "documents": indexed}), encoding="utf-8")
        return len(indexed)

    def search(self, query: str, source_types: Optional[set[str]] = None,
               case_id: Optional[str] = None, top_k: int = 30) -> list[dict]:
        if not query or not self.provider.available:
            return []
        documents = self.load()
        if not documents:
            return []
        query_vector = self.provider.embed([query])[0]
        results = []
        for document in documents:
            if source_types and document.get("source_type") not in source_types:
                continue
            if case_id is not None and document.get("case_id") != case_id:
                continue
            score = _cosine_similarity(query_vector, document.get("vector", []))
            results.append({**document, "score": score})
        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


if __name__ == "__main__":
    from database import SessionLocal

    with SessionLocal() as session:
        count = SemanticIndex().rebuild(session)
    print(f"Indexed {count} records")