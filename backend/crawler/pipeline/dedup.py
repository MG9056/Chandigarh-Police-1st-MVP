from hashlib import sha256
from sqlalchemy.orm import Session

from crawler.models.raw_record import RawRecord


class Deduplicator:
    """
    Computes SHA-256 content hashes and checks DB for duplicates to avoid redundant processing.
    """

    @staticmethod
    def compute_hash(content: str | bytes) -> str:
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content
        return sha256(content_bytes).hexdigest()

    @staticmethod
    def is_duplicate(content_hash: str, db: Session) -> bool:
        existing = db.query(RawRecord).filter(RawRecord.content_hash == content_hash).first()
        return existing is not None
