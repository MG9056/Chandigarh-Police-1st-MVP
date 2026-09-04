from datetime import datetime
from hashlib import sha256
from typing import Any, Dict


class EvidenceTagger:
    """
    Enforces evidentiary provenance metadata on every RawRecord prior to DB persistence.
    Validates presence of url, fetched_at, run_id, and content_hash.
    Computes content_hash over raw fetched content bytes before any cleaning.
    """

    @staticmethod
    def compute_raw_content_hash(raw_text_or_bytes: str | bytes) -> str:
        if isinstance(raw_text_or_bytes, str):
            content_bytes = raw_text_or_bytes.encode("utf-8")
        else:
            content_bytes = raw_text_or_bytes or b""
        return sha256(content_bytes).hexdigest()

    @classmethod
    def tag_and_validate(cls, record_data: Dict[str, Any], run_id: Any) -> Dict[str, Any]:
        raw_content = record_data.get("raw_text") or ""
        content_hash = cls.compute_raw_content_hash(raw_content)

        record_data["run_id"] = str(run_id) if run_id else None
        record_data["content_hash"] = content_hash

        # Enforce validation of mandatory provenance fields
        missing_fields = []
        for field in ("url", "fetched_at", "run_id", "content_hash"):
            if not record_data.get(field):
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(f"RawRecord failed provenance validation. Missing fields: {', '.join(missing_fields)}")

        return record_data
